import uuid
import hashlib
import secrets
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Security, Body, Response, status, Cookie
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from pydantic import EmailStr # इंश्योर pydantic is installed with email validation support
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import get_db
from app.models import ApiKey, User
from app import schemas # Import Pydantic schemas from app.schemas
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES # Import JWT settings
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

# --- User Database Utilities ---
def get_user_by_email(db: Session, email: EmailStr) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

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
    db_user = get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed_password = hash_password(user_in.password)

    # Create a unique external-facing user_id (User.user_id in model)
    external_user_id = f"user_{secrets.token_hex(8)}"
    while db.query(User).filter(User.user_id == external_user_id).first():
         external_user_id = f"user_{secrets.token_hex(8)}"

    new_user = User(
        user_id=external_user_id,
        email=user_in.email,
        hashed_password=hashed_password,
        name=user_in.email.split('@')[0] # Default name from email prefix
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
    form_data: schemas.UserLogin, # Using UserLogin schema for email/password in body
    db: Session = Depends(get_db)
):
    user = get_user_by_email(db, email=form_data.email)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user.id)}, # 'sub' is the User.id (UUID PK)
        expires_delta=access_token_expires
    )

    response.set_cookie(
        key="openmemory_access_token",
        value=access_token,
        httponly=True, # Makes it inaccessible to JavaScript
        max_age=int(access_token_expires.total_seconds()),
        samesite="lax", # Basic CSRF protection
        secure=False,  # In production, set to True (requires HTTPS)
        path="/",
    )
    return {"message": "Login successful", "user_id": str(user.id), "email": user.email}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("openmemory_access_token", path="/")
    return {"message": "Logout successful"}

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

    input_key_hashed = hashlib.sha256((api_key_header + db_api_key.salt).encode()).hexdigest()
    if not secrets.compare_digest(input_key_hashed, db_api_key.hashed_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API Key: Verification failed.")

    # TODO: Optionally update last_used_at for db_api_key
    return db_api_key

# --- API Key Scope Verification Dependency (for X-API-Key header auth) ---
def verify_api_key_scope(required_scopes: List[str]):
    async def _verify_scope(api_key: ApiKey = Depends(get_api_key)): # Uses X-API-Key
        if not api_key.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions: Key has no scopes defined.")

        key_scopes = set(api_key.scopes.split(','))
        for required_scope in required_scopes:
            if required_scope not in key_scopes:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: Scope '{required_scope}' missing."
                )
        return api_key
    return _verify_scope

# --- Scopes Definition ---
SCOPES_KEY_READ = "keys:read"
SCOPES_KEY_MANAGE = "keys:manage" # Includes create, delete, potentially update
SCOPES_MEMORIES_READ = "memories:read"
SCOPES_MEMORIES_WRITE = "memories:write"
DEFAULT_API_KEY_SCOPES = [SCOPES_MEMORIES_READ, SCOPES_MEMORIES_WRITE]


# --- API Key Management Endpoints (protected by API Key scopes) ---
@router.post("/keys", response_model_exclude_none=True)
@limiter.limit("20/minute") # Example: 20 key creation attempts per minute per IP (or per API key if key_func changes)
async def create_api_key(
    request: Request, # Add request for limiter
    name: str = Body(None),
    scopes: List[str] = Body(None),
    db: Session = Depends(get_db),
    # This endpoint is protected by an API key that must have "keys:manage" scope.
    # The user_id for the new key will be the user_id of the managing_api_key.
    managing_api_key: ApiKey = Depends(verify_api_key_scope([SCOPES_KEY_MANAGE]))
):
    user_id_for_new_key = managing_api_key.user_id

    plain_api_key = secrets.token_urlsafe(32)
    salt = secrets.token_urlsafe(16)
    key_prefix = plain_api_key[:8]
    hashed_key = hashlib.sha256((plain_api_key + salt).encode()).hexdigest()

    if scopes is None or not scopes:
        assigned_scopes_str = ",".join(DEFAULT_API_KEY_SCOPES)
    else:
        # TODO: Validate that managing_api_key has privileges to grant all requested scopes.
        # For now, allow assigning any requested scopes if managing_api_key is valid.
        assigned_scopes_str = ",".join(scopes)

    new_api_key_entry = ApiKey(
        user_id=user_id_for_new_key,
        name=name,
        hashed_key=hashed_key,
        salt=salt,
        key_prefix=key_prefix,
        scopes=assigned_scopes_str
    )
    db.add(new_api_key_entry)
    db.commit()
    db.refresh(new_api_key_entry)

    return {
        "api_key": plain_api_key, "id": new_api_key_entry.id, "name": new_api_key_entry.name,
        "key_prefix": new_api_key_entry.key_prefix, "scopes": new_api_key_entry.scopes.split(',')
    }

@router.get("/keys", response_model_exclude_none=True)
async def list_api_keys(
    db: Session = Depends(get_db),
    # Protected by an API key that must have "keys:read" scope.
    # Lists keys belonging to the user of the requesting_api_key.
    requesting_api_key: ApiKey = Depends(verify_api_key_scope([SCOPES_KEY_READ]))
):
    keys_query_result = db.query(
        ApiKey.id, ApiKey.name, ApiKey.key_prefix, ApiKey.scopes,
        ApiKey.is_active, ApiKey.created_at, ApiKey.last_used_at, ApiKey.expires_at
    ).filter(ApiKey.user_id == requesting_api_key.user_id).all()

    return [
        {
            "id": k.id, "name": k.name, "key_prefix": k.key_prefix,
            "scopes": k.scopes.split(',') if k.scopes else [],
            "is_active": k.is_active, "created_at": k.created_at,
            "last_used_at": k.last_used_at, "expires_at": k.expires_at
        }
        for k in keys_query_result
    ]

@router.delete("/keys/{key_id}")
async def delete_api_key(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    # Protected by an API key that must have "keys:manage" scope.
    # Deletes a key belonging to the user of the requesting_api_key.
    requesting_api_key: ApiKey = Depends(verify_api_key_scope([SCOPES_KEY_MANAGE]))
):
    key_to_delete = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == requesting_api_key.user_id # Key must belong to the same user
    ).first()

    if not key_to_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="API Key not found or not authorized to delete for this user.")

    db.delete(key_to_delete)
    db.commit()
    return {"message": "API Key deleted successfully"}

# Note on `get_or_create_user`: This was removed as per the task's implication that
# users are now explicitly registered. API keys are created by users for themselves (via an existing key with scope)
# or potentially by an admin (not covered here). The `user_id` for an ApiKey is always a valid User.id (PK).
