import datetime
import os # For environment variables
from fastapi import FastAPI, Request # Request for rate limiter key_func
from slowapi import Limiter, _rate_limit_exceeded_handler # Rate limiting
from slowapi.util import get_remote_address # Rate limiting
from slowapi.errors import RateLimitExceeded # Rate limiting
from slowapi.middleware import SlowAPIMiddleware # If using middleware application
# For direct application to app: from slowapi.extension import FastAPILimiter

from app.database import engine, Base, SessionLocal
from app.mcp_server import setup_mcp_server
from app.routers import memories_router, apps_router, stats_router, config_router
from app.routers import auth as auth_router
from app.routers.auth import hash_password # Import for default user password hashing
from app.routers import a2a as a2a_router # New A2A import
from fastapi_pagination import add_pagination
from fastapi.middleware.cors import CORSMiddleware
from app.models import User, App
from uuid import uuid4
from app.config import USER_ID, DEFAULT_APP_ID

# Initialize Rate Limiter
# Using REDIS_URL from env for storage, fallback to memory for local dev/testing
# Ensure REDIS_URL is set in your environment for production: e.g., "redis://localhost:6379"
redis_url = os.getenv("REDIS_URL", "memory://")
limiter = Limiter(key_func=get_remote_address, storage_uri=redis_url, strategy="fixed-window") # strategy can be configured

app = FastAPI(title="OpenMemory API")

# Add state for the limiter and an exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply SlowAPIMiddleware if you want to apply limits globally or by route pattern in some cases
# However, for specific endpoint decorators, just initializing Limiter and adding to app.state is enough.
# app.add_middleware(SlowAPIMiddleware) # Not strictly needed if only using decorators

# CORS Configuration
allowed_origins_csv = os.getenv("ALLOWED_ORIGINS_CSV", "http://localhost:3000,http://127.0.0.1:3000")
allowed_origins_list = [origin.strip() for origin in allowed_origins_csv.split(',')]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_credentials=True, # Important for cookies
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], # Specify methods
    allow_headers=["Content-Type", "X-API-Key", "Authorization"], # Specify headers
)

# Create all tables
Base.metadata.create_all(bind=engine)

# TODO: Apply @limiter.limit decorators to specific endpoints in their respective router files.
# Example for auth.py:
# from main import limiter # (Adjust import path if main.limiter is not directly accessible)
# @router.post("/login")
# @limiter.limit("5/minute")
# async def login_for_access_token(...): ...
# This needs to be done in openmemory/api/app/routers/auth.py for the specific routes.

# Check for USER_ID and create default user if needed
def create_default_user():
    db = SessionLocal()
    try:
        # Check if user exists
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            # Create default user
            # Create default user
            default_email = f"{USER_ID}@example.com"
            default_password = "defaultpassword" # Consider making this more secure or configurable

            # Check if email already exists (e.g. if USER_ID is "admin" and admin@example.com is taken)
            existing_email_user = db.query(User).filter(User.email == default_email).first()
            if existing_email_user:
                print(f"Default user email {default_email} already exists. Skipping default user creation with this email.")
                # Potentially link existing email user to USER_ID if appropriate, or handle error
                return


            user = User(
                id=uuid4(),
                user_id=USER_ID,
                name="Default User",
                email=default_email,
                hashed_password=hash_password(default_password),
                created_at=datetime.datetime.now(datetime.UTC)
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


def create_default_app():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == USER_ID).first()
        if not user:
            return

        # Check if app already exists
        existing_app = db.query(App).filter(
            App.name == DEFAULT_APP_ID,
            App.owner_id == user.id
        ).first()

        if existing_app:
            return

        app = App(
            id=uuid4(),
            name=DEFAULT_APP_ID,
            owner_id=user.id,
            created_at=datetime.datetime.now(datetime.UTC),
            updated_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(app)
        db.commit()
    finally:
        db.close()

# Create default user on startup
create_default_user()
create_default_app()

# Setup MCP server
setup_mcp_server(app)

from app.routers import keys as keys_router # Import the new keys router

# Include routers
app.include_router(memories_router)
app.include_router(apps_router)
app.include_router(stats_router)
app.include_router(config_router)
app.include_router(auth_router.router)
app.include_router(keys_router.router) # Include the new keys router
app.include_router(a2a_router.router) # Include the A2A router

# Add pagination support
add_pagination(app)
