import uuid
import hashlib
import secrets
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Body, Request # Added Request
from sqlalchemy.orm import Session

from app.database import get_db
# Attempt to import limiter from main.py, similar to auth.py
try:
    from app.main import limiter
except ImportError:
    class DummyLimiter: # Fallback if direct import from main is tricky
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = DummyLimiter()

from app.models import User, ApiKey
from app import schemas #Pydantic schemas
# Assuming get_current_user is in auth.py and accessible via relative import
from .auth import get_current_user


# --- Scopes Definition (copied from auth.py for now, consider centralizing) ---
SCOPES_KEY_READ = "keys:read" # Kept for reference if needed, but this router manages user's own keys
SCOPES_KEY_MANAGE = "keys:manage" # Kept for reference
SCOPES_MEMORIES_READ = "memories:read"
SCOPES_MEMORIES_WRITE = "memories:write"
SCOPES_A2A_DISPATCH = "a2a:dispatch"
SCOPES_CONFIG_READ = "config:read"
SCOPES_CONFIG_WRITE = "config:write"
SCOPES_APPS_READ = "apps:read"
SCOPES_APPS_WRITE = "apps:write"
SCOPES_STATS_READ = "stats:read"

DEFAULT_API_KEY_SCOPES = [
    SCOPES_MEMORIES_READ,
    SCOPES_MEMORIES_WRITE,
    SCOPES_A2A_DISPATCH,
    SCOPES_CONFIG_READ,
    SCOPES_CONFIG_WRITE,
    SCOPES_APPS_READ,
    SCOPES_APPS_WRITE,
    SCOPES_STATS_READ,
]

router = APIRouter(
    prefix="/api/v1/keys",
    tags=["API Keys"],
    dependencies=[Depends(get_current_user)] # All endpoints here require JWT authenticated user
)

@router.post("/", response_model=schemas.ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
async def create_user_api_key(
    request: Request, # Added for limiter context
    key_in: schemas.ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validate expires_at if provided
    if key_in.expires_at and key_in.expires_at <= datetime.now(datetime.timezone.utc).replace(tzinfo=None):
        # Ensure expires_at is timezone-naive if datetime.now() is, or make them both aware
        # For simplicity, assuming UTC for expires_at if provided, and comparing with current UTC time
        # If key_in.expires_at is already timezone-aware, this comparison is fine.
        # If it's naive, ensure it's interpreted as UTC.
        # FastAPI usually handles this based on Pydantic model. Let's assume it's UTC.
        if key_in.expires_at <= datetime.utcnow(): # Simpler comparison if both are naive UTC
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expiration date must be in the future.")


    plain_api_key = secrets.token_urlsafe(32)
    key_prefix = plain_api_key[:8]
    hashed_key = hashlib.sha256(plain_api_key.encode()).hexdigest()

    assigned_scopes: List[str]
    if key_in.scopes is None or not key_in.scopes:
        assigned_scopes = DEFAULT_API_KEY_SCOPES
    else:
        # TODO: Optional: Validate if the current_user has permissions to grant all requested scopes
        # For now, any authenticated user can create keys with any of the DEFAULT_API_KEY_SCOPES or subset they specify
        # We could also intersect key_in.scopes with a list of grantable_scopes by the user.
        assigned_scopes = key_in.scopes

    new_api_key_entry = ApiKey(
        user_id=current_user.id, # Associated with the current authenticated user
        name=key_in.name,
        hashed_key=hashed_key,
        key_prefix=key_prefix,
        scopes=assigned_scopes,
        expires_at=key_in.expires_at
    )
    db.add(new_api_key_entry)
    db.commit()
    db.refresh(new_api_key_entry)

    return schemas.ApiKeyCreateResponse(
        api_key=plain_api_key, # Return the plain text key
        id=new_api_key_entry.id,
        name=new_api_key_entry.name,
        key_prefix=new_api_key_entry.key_prefix,
        scopes=new_api_key_entry.scopes,
        expires_at=new_api_key_entry.expires_at,
        created_at=new_api_key_entry.created_at,
        is_active=new_api_key_entry.is_active
    )

@router.get("/", response_model=List[schemas.ApiKeyListResponseItem])
@limiter.limit("60/minute")
async def list_user_api_keys(
    request: Request, # Added for limiter context
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    keys_query_result = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).all()

    # Map the ORM objects to Pydantic models
    response_items = []
    for k in keys_query_result:
        response_items.append(schemas.ApiKeyListResponseItem(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            scopes=k.scopes if k.scopes else [], # Ensure scopes is a list
            is_active=k.is_active,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            expires_at=k.expires_at
        ))
    return response_items

@router.delete("/{key_prefix}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_user_api_key(
    request: Request, # Added for limiter context
    key_prefix: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    key_to_delete = db.query(ApiKey).filter(
        ApiKey.key_prefix == key_prefix,
        ApiKey.user_id == current_user.id
    ).first()

    if not key_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API Key not found or you do not have permission to delete it."
        )

    db.delete(key_to_delete)
    db.commit()
    return None # For 204 No Content
