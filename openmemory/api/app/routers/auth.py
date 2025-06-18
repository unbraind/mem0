import uuid
import hashlib
import secrets
import os # Added for environment variable access
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Security, Body, Response, status, Cookie
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Tuple # For type hinting
from pydantic import EmailStr # इंश्योर pydantic is installed with email validation support
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import get_db
from app.models import ApiKey, User
from app import schemas # Import Pydantic schemas from app.schemas
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS # Import JWT settings
from fastapi import Request # Required for limiter if key_func needs request
# Attempt to import limiter from main.py. This might need adjustment if circular dependency.
# A better pattern might be to have limiter in a shared core/extensions.py.
try:
    from app.main import limiter
except ImportError: # Fallback if direct import from main is tricky (e.g. app instance not yet fully formed)
    # This fallback means rate limiting won't be applied if limiter isn't found.
    # In a real app, this should be resolved by better structuring.
    # For this exercise, we'll try and if it fails at runtime, it means refactor is needed.
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = DummyLimiter()


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

# --- Password Utilities ---
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# --- JWT Utilities ---
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    # Optionally, add a "type": "refresh" claim if needed for strict differentiation,
    # but often the separate refresh endpoint implies its type.
    # to_encode.update({"type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- User Database Utilities ---
def get_user_by_email(db: Session, email: EmailStr) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()

def get_user_by_id(db: Session, user_id: uuid.UUID) -> Optional[User]: # user_id is User.id (PK, UUID)
    return db.query(User).filter(User.id == user_id).first()

# --- Current User Dependency (JWT Cookie Based) ---
async def get_current_user(
    token: Optional[str] = Cookie(None, alias="openmemory_access_token"),
    db: Session = Depends(get_db)
) -> User:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: No token provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: Optional[str] = payload.get("sub") # 'sub' claim stores User.id (UUID) as string
        if user_id_str is None:
            raise credentials_exception

        try:
            user_uuid = uuid.UUID(user_id_str) # Validate that 'sub' is a valid UUID string
        except ValueError:
            raise credentials_exception # Invalid UUID format in token

        # TokenData schema expects user_id (which corresponds to 'sub')
        token_data = schemas.TokenData(user_id=user_id_str)
    except JWTError:
        raise credentials_exception

    # Fetch user by User.id (UUID)
    user = get_user_by_id(db, user_id=uuid.UUID(token_data.user_id)) # type: ignore # Ensure UUID(token_data.user_id)
    if user is None:
        raise credentials_exception
    return user

# --- Web UI Auth Endpoints (JWT Cookie Based) ---
@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute") # Example: 10 registration attempts per minute per IP
async def register_user(request: Request, user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if email already exists
    db_user_by_email = get_user_by_email(db, email=user_in.email)
    if db_user_by_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    # Check if username already exists
    db_user_by_username = db.query(User).filter(User.username == user_in.username).first()
    if db_user_by_username:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")

    hashed_password = hash_password(user_in.password)

    new_user = User(
        username=user_in.username, # Use username from input
        email=user_in.email,
        hashed_password=hashed_password,
        name=user_in.email.split('@')[0] # Default name from email prefix, can be updated later if needed
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login") # Returns response with cookie, and a JSON message
@limiter.limit("10/minute") # Example: 10 login attempts per minute per IP
async def login_for_access_token(
    request: Request,
    response: Response,
    form_data: schemas.UserLogin,
    db: Session = Depends(get_db)
):
    user: Optional[User] = None
    if form_data.username:
        user = get_user_by_username(db, username=form_data.username)
    elif form_data.email:
        user = get_user_by_email(db, email=form_data.email)
    else:
        # This case should ideally be caught by Pydantic model validation in UserLogin schema
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either username or email must be provided.",
        )

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username, email, or password", # More generic message
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    # Create refresh token
    refresh_token_expires = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = create_refresh_token(
        data={"sub": str(user.id)}, # Refresh token also contains user ID
        expires_delta=refresh_token_expires
    )

    # Determine cookie security flags based on environment
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    cookie_secure = ENVIRONMENT == "production"
    cookie_samesite = "lax" # Or "strict" if appropriate for your app's flow

    # Set refresh token in HttpOnly cookie
    response.set_cookie(
        key="openmemory_refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=int(refresh_token_expires.total_seconds()),
        samesite=cookie_samesite,
        secure=cookie_secure,
        path="/auth",  # Be specific with path, e.g., /auth or /api/auth
    )

    # Return access token in response body
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response):
    # Clear both access token cookie (if it was set) and refresh token cookie
    response.delete_cookie("openmemory_access_token", path="/") # If previously set
    response.delete_cookie("openmemory_refresh_token", path="/auth")
    return {"message": "Logout successful"}

@router.post("/refresh", response_model=schemas.Token)
@limiter.limit("5/minute") # Example: 5 refresh attempts per minute per IP/user
async def refresh_access_token(
    request: Request, # For limiter
    response: Response, # To potentially update cookie if rotating refresh token
    openmemory_refresh_token: Optional[str] = Cookie(None), # Extract refresh token from cookie
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials, please log in again",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not openmemory_refresh_token:
        raise credentials_exception

    try:
        payload = jwt.decode(openmemory_refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: Optional[str] = payload.get("sub")
        # Optionally check for a "type": "refresh" claim if you added it during token creation
        # token_type: Optional[str] = payload.get("type")
        # if token_type != "refresh":
        #     raise credentials_exception

        if user_id_str is None:
            raise credentials_exception

        try:
            user_uuid = uuid.UUID(user_id_str)
        except ValueError:
            raise credentials_exception # Invalid UUID format in token

        token_data = schemas.TokenData(user_id=user_id_str) # Validate payload structure
    except JWTError: # Covers expired signature, invalid signature, etc.
        raise credentials_exception

    user = get_user_by_id(db, user_id=user_uuid)
    if user is None:
        raise credentials_exception

    # Create new access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


# --- API Key Functionality (Header Based Auth, X-API-Key) ---
API_KEY_NAME = "X-API-Key"
api_key_header_auth_scheme = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key( # This is for X-API-Key header based authentication
    api_key_header: str = Security(api_key_header_auth_scheme),
    db: Session = Depends(get_db),
):
    if not api_key_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authenticated: No API key provided.")

    if len(api_key_header) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid API Key format: Key too short.")

    key_prefix_to_lookup = api_key_header[:8]
    db_api_key = db.query(ApiKey).filter(ApiKey.key_prefix == key_prefix_to_lookup).first()

    if not db_api_key or not db_api_key.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or inactive API Key.")

    # Hash the provided API key directly (no salt from DB)
    hashed_input_key = hashlib.sha256(api_key_header.encode()).hexdigest()
    if not secrets.compare_digest(hashed_input_key, db_api_key.hashed_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key: Verification failed.")

    # TODO: Optionally update last_used_at for db_api_key
    return db_api_key

# --- API Key Scope Verification Dependency (for X-API-Key header auth) ---
# This function and get_api_key are related to *using* an API key for authentication,
# so they remain in auth.py.
def verify_api_key_scope(required_scopes: List[str]):
    async def _verify_scope(api_key: ApiKey = Depends(get_api_key)): # Uses X-API-Key
        # 1. Check for expiration
        if api_key.expires_at and datetime.now(timezone.utc) > api_key.expires_at:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="API Key has expired.")

        # 2. Check for scopes
        # If required_scopes is empty, any key (even one with no scopes) is technically valid from a scope perspective.
        if not required_scopes:
            return api_key # No specific scopes required, so key is valid in this context.

        # If scopes are required, but the key has none, it's an issue.
        # api_key.scopes is now a list (or should be, from JSON).
        if not api_key.scopes: # Should be an empty list if no scopes, not None, due to model default.
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions: Key has no scopes defined, but scopes are required.")

        key_scopes = set(api_key.scopes if api_key.scopes else []) # Ensure it's a set, handle None if old data exists
        for required_scope in required_scopes:
            if required_scope not in key_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: Scope '{required_scope}' missing."
                )
        return api_key
    return _verify_scope


# --- Bearer Token API Key Authentication ---
bearer_scheme = HTTPBearer(auto_error=False)

async def get_user_and_scopes_from_bearer_api_key(
    token: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db)
) -> Tuple[User, List[str]]:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated (No Bearer token provided)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    plain_api_key = token.credentials
    hashed_token = hashlib.sha256(plain_api_key.encode()).hexdigest()

    db_api_key = db.query(ApiKey).filter(ApiKey.hashed_key == hashed_token).first()

    if not db_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key (key not found)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not db_api_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if db_api_key.expires_at and datetime.now(timezone.utc).replace(tzinfo=None) > db_api_key.expires_at.replace(tzinfo=None):
        # Ensure comparison is between naive datetimes if db_api_key.expires_at is naive
        # Or make both timezone-aware (UTC)
        # Assuming expires_at is stored as naive UTC or converted to naive UTC for comparison
        if datetime.utcnow() > db_api_key.expires_at: # Simpler if both are naive UTC
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API Key has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

    user = db.query(User).filter(User.id == db_api_key.user_id).first()
    if not user:
        # This case should ideally not happen if DB integrity is maintained
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Associated user not found for API Key",
        )

    # Assuming db_api_key.scopes is already a list of strings (e.g., from JSON column)
    return user, db_api_key.scopes if db_api_key.scopes else []


def verify_bearer_api_key_scope(required_scopes: List[str]):
    async def _verify_scope_bearer(
        user_and_scopes: Tuple[User, List[str]] = Depends(get_user_and_scopes_from_bearer_api_key)
    ) -> Tuple[User, List[str]]:
        _, key_scopes = user_and_scopes

        if not required_scopes: # If no specific scopes are required by the endpoint
            return user_and_scopes

        current_key_scopes = set(key_scopes)
        for required_scope in required_scopes:
            if required_scope not in current_key_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: Scope '{required_scope}' missing from API Key."
                )
        return user_and_scopes

# Note: The Scopes Definitions (SCOPES_KEY_READ, etc.) and DEFAULT_API_KEY_SCOPES
# have been removed from here as they are now primarily relevant to the new keys.py router
# or should be centralized if shared more broadly.
# API Key Management Endpoints (POST, GET, DELETE for /keys) have also been removed
# and are now in keys.py.

# Note on `get_or_create_user`: This was removed as per the task's implication that
# users are now explicitly registered. API keys are created by users for themselves (via an existing key with scope)
# or potentially by an admin (not covered here). The `user_id` for an ApiKey is always a valid User.id (PK).
# The `managing_api_key: ApiKey = Depends(verify_api_key_scope([SCOPES_KEY_MANAGE]))`
# type dependency in the old create_api_key used SCOPES_KEY_MANAGE.
# The new keys.py router uses JWT auth for the user to manage their *own* keys,
# so this specific cross-key management scope isn't used there by default.
# If admin-level key management (managing other users' keys or assigning very privileged scopes)
# were needed, it would typically be a separate set of endpoints with different authorization.
