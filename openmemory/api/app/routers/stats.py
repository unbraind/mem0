from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Memory, App, MemoryState, ApiKey
from app.routers.auth import verify_api_key_scope, SCOPES_STATS_READ


router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

@router.get("/")
async def get_profile( # Renamed from get_stats to avoid conflict if there was a get_stats elsewhere
    user_id: str, # TODO: Validate this user_id against current_api_key.user_id
    db: Session = Depends(get_db),
    current_api_key: ApiKey = Depends(verify_api_key_scope([SCOPES_STATS_READ]))
):
    # Note: user_id from query should be validated against current_api_key.user_id
    # to ensure the key is used for its own user's stats.
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Add check: if user.id != current_api_key.user_id: raise HTTPException(403, "Not authorized")

    # Get total number of memories
    total_memories = db.query(Memory).filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted).count()

    # Get total number of apps
    apps = db.query(App).filter(App.owner == user)
    total_apps = apps.count()

    return {
        "total_memories": total_memories,
        "total_apps": total_apps,
        "apps": apps.all()
    }

