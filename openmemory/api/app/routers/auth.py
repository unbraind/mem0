import uuid
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ApiKey, User
from app.utils.auth import get_or_create_user # Assuming this utility exists or will be created

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(
    api_key_header: str = Security(api_key_header),
    db: Session = Depends(get_db),
):
    if not api_key_header:
        raise HTTPException(status_code=403, detail="Not authenticated")

    api_key = db.query(ApiKey).filter(ApiKey.key == api_key_header).first()
    if not api_key or not api_key.is_active:
        raise HTTPException(status_code=403, detail="Invalid or inactive API Key")

    # TODO: Update last_used_at for the key
    return api_key

@router.post("/keys", response_model_exclude_none=True)
async def create_api_key(
    name: str = None,
    db: Session = Depends(get_db),
    # TODO: Add current_user dependency once user authentication is set up
    # current_user: User = Depends(get_current_user),
):
    """
    Create a new API key.
    """
    # For now, associate with a default/test user or get/create one
    # This part needs to be adjusted based on actual user management
    user = get_or_create_user(db, "default_user_id_for_api_key") # Replace with actual user_id or logic

    new_key = ApiKey(user_id=user.id, name=name)
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    return {"api_key": new_key.key, "name": new_key.name, "id": new_key.id}

@router.get("/keys", response_model_exclude_none=True)
async def list_api_keys(
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user), # TODO
    api_key: ApiKey = Depends(get_api_key) # Secure this endpoint
):
    """
    List all API keys for the current user.
    """
    # keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).all() # TODO
    keys = db.query(ApiKey).filter(ApiKey.user_id == api_key.user_id).all() # Temp: list keys for authenticated user
    return keys

@router.delete("/keys/{key_id}")
async def delete_api_key(
    key_id: uuid.UUID,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user), # TODO
    api_key: ApiKey = Depends(get_api_key) # Secure this endpoint
):
    """
    Delete an API key.
    """
    # key_to_delete = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == current_user.id).first() # TODO
    key_to_delete = db.query(ApiKey).filter(ApiKey.id == key_id, ApiKey.user_id == api_key.user_id).first() # Temp
    if not key_to_delete:
        raise HTTPException(status_code=404, detail="API Key not found")

    db.delete(key_to_delete)
    db.commit()
    return {"message": "API Key deleted successfully"}
