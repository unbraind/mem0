import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from uuid import uuid4

from app.main import app # Main FastAPI app
from app.models import User
from app.schemas import UserCreate # UserLogin already imported by implication if needed
from app.dependencies import get_db # To override if using test DB sessions explicitly
from app.database import Base, engine # For creating tables if using in-memory DB for tests

# This would typically be in conftest.py
# For now, let's assume a TestClient fixture 'client' is available
# and a 'db_session' fixture provides a transactional DB session.

def get_random_user_payload():
    rand_id = uuid4().hex[:8]
    return {
        "username": f"testuser_{rand_id}",
        "email": f"test_{rand_id}@example.com",
        "password": "testpassword123"
    }

def test_register_user_success(client: TestClient, db_session: Session):
    payload = get_random_user_payload()
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == payload["email"]
    assert data["username"] == payload["username"]
    assert "id" in data

    user_in_db = db_session.query(User).filter(User.email == payload["email"]).first()
    assert user_in_db is not None
    assert user_in_db.username == payload["username"]

def test_register_user_duplicate_username(client: TestClient, db_session: Session):
    payload = get_random_user_payload()
    # Create user first
    client.post("/auth/register", json=payload)

    # Attempt to register again with same username, different email
    payload_new_email = payload.copy()
    payload_new_email["email"] = f"new_{uuid4().hex[:6]}@example.com"
    response = client.post("/auth/register", json=payload_new_email)
    assert response.status_code == 400
    assert "Username already registered" in response.json()["detail"]

def test_register_user_duplicate_email(client: TestClient, db_session: Session):
    payload = get_random_user_payload()
    # Create user first
    client.post("/auth/register", json=payload)

    # Attempt to register again with same email, different username
    payload_new_username = payload.copy()
    payload_new_username["username"] = f"newuser_{uuid4().hex[:6]}"
    response = client.post("/auth/register", json=payload_new_username)
    assert response.status_code == 400
    assert "Email already registered" in response.json()["detail"]

def test_login_with_username_success(client: TestClient, db_session: Session):
    user_payload = get_random_user_payload()
    client.post("/auth/register", json=user_payload) # Register user

    login_payload = {
        "username": user_payload["username"],
        "password": user_payload["password"]
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Check for refresh token cookie
    assert "openmemory_refresh_token" in response.cookies
    refresh_cookie = response.cookies["openmemory_refresh_token"]
    assert "HttpOnly" in refresh_cookie.split('; ') # Varies by client lib, this is common
    # assert "Secure" in refresh_cookie # Only if ENVIRONMENT=production in test
    assert "Path=/auth" in refresh_cookie # Path set in auth.py

def test_login_with_email_success(client: TestClient, db_session: Session):
    user_payload = get_random_user_payload()
    client.post("/auth/register", json=user_payload) # Register user

    login_payload = {
        "email": user_payload["email"], # Login with email
        "password": user_payload["password"]
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "openmemory_refresh_token" in response.cookies

def test_login_incorrect_password(client: TestClient, db_session: Session):
    user_payload = get_random_user_payload()
    client.post("/auth/register", json=user_payload)

    login_payload = {
        "username": user_payload["username"],
        "password": "wrongpassword"
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 401
    assert "Incorrect username, email, or password" in response.json()["detail"]

def test_login_non_existent_user(client: TestClient):
    login_payload = {
        "username": "nonexistentuser",
        "password": "testpassword123"
    }
    response = client.post("/auth/login", json=login_payload)
    assert response.status_code == 401 # Or 404 depending on backend logic, 401 is common for auth
    assert "Incorrect username, email, or password" in response.json()["detail"]

def test_refresh_token_success(client: TestClient):
    user_payload = get_random_user_payload()
    client.post("/auth/register", json=user_payload)

    login_payload = {"username": user_payload["username"], "password": user_payload["password"]}
    login_response = client.post("/auth/login", json=login_payload)
    assert login_response.status_code == 200
    assert "openmemory_refresh_token" in login_response.cookies

    # The TestClient automatically handles cookies, so subsequent requests will include it.
    refresh_response = client.post("/auth/refresh")
    assert refresh_response.status_code == 200
    data = refresh_response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_refresh_token_no_cookie(client: TestClient):
    # Create a new client instance that doesn't share cookies from previous requests in this function
    clean_client = TestClient(app)
    refresh_response = clean_client.post("/auth/refresh")
    assert refresh_response.status_code == 401 # Expecting 401 if no refresh token cookie
    assert "Not authenticated" in refresh_response.json()["detail"] # Or specific message from refresh endpoint

def test_refresh_token_invalid_cookie(client: TestClient):
    # Create a new client instance
    clean_client = TestClient(app)
    # Set an invalid cookie
    clean_client.cookies.set("openmemory_refresh_token", "invalidtokenvalue")
    refresh_response = clean_client.post("/auth/refresh")
    assert refresh_response.status_code == 401
    assert "Could not validate credentials" in refresh_response.json()["detail"]

# TODO: Consider adding a test for password hashing algorithm update (e.g. old bcrypt hash still works for login)
# This would require manually inserting a user with a bcrypt hash.
# For now, Argon2 is default for new users.
