import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typing import Dict, List, Any
from uuid import uuid4
import time # For unique names/emails if needed, and checking expiry

from app.main import app
from app.models import User, ApiKey
from app.schemas import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyListResponseItem
from app.database import Base, engine

# This fixture creates a new user, logs them in, and returns auth headers + user object
@pytest.fixture(scope="function")
def authenticated_user_with_token(client: TestClient, db_session: Session) -> Dict[str, Any]:
    rand_id = uuid4().hex[:8]
    user_payload = {
        "username": f"keyuser_{rand_id}",
        "email": f"keyuser_{rand_id}@example.com",
        "password": "testpassword123"
    }
    # Register user
    reg_response = client.post("/auth/register", json=user_payload)
    assert reg_response.status_code == 201
    user_data = reg_response.json()

    # Login user
    login_payload = {"username": user_payload["username"], "password": user_payload["password"]}
    login_response = client.post("/auth/login", json=login_payload)
    assert login_response.status_code == 200
    token_data = login_response.json()

    return {
        "headers": {"Authorization": f"Bearer {token_data['access_token']}"},
        "user": user_data # Contains id, username, email from registration response
    }

def test_create_api_key_default_scopes(client: TestClient, db_session: Session, authenticated_user_with_token: Dict[str, Any]):
    headers = authenticated_user_with_token["headers"]
    user_id = authenticated_user_with_token["user"]["id"]

    key_create_payload = {"name": "Test Key Default Scopes"}
    response = client.post("/api/v1/keys", json=key_create_payload, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert "api_key" in data
    assert "key_prefix" in data
    assert data["name"] == "Test Key Default Scopes"
    # Check default scopes (assuming DEFAULT_API_KEY_SCOPES is known or check it's a list)
    assert isinstance(data["scopes"], list)
    assert len(data["scopes"]) > 0 # Assuming default scopes are not empty

    db_key = db_session.query(ApiKey).filter(ApiKey.key_prefix == data["key_prefix"]).first()
    assert db_key is not None
    assert db_key.user_id == user_id
    assert db_key.name == "Test Key Default Scopes"
    assert len(db_key.hashed_key) == 64 # SHA256 hash length

def test_create_api_key_custom_scopes(client: TestClient, db_session: Session, authenticated_user_with_token: Dict[str, Any]):
    headers = authenticated_user_with_token["headers"]
    custom_scopes = ["memories:read", "custom_scope_test"]
    key_create_payload = {"name": "Test Key Custom Scopes", "scopes": custom_scopes}

    response = client.post("/api/v1/keys", json=key_create_payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Key Custom Scopes"
    assert set(data["scopes"]) == set(custom_scopes)

    db_key = db_session.query(ApiKey).filter(ApiKey.key_prefix == data["key_prefix"]).first()
    assert db_key is not None
    assert set(db_key.scopes) == set(custom_scopes)

def test_list_api_keys(client: TestClient, db_session: Session, authenticated_user_with_token: Dict[str, Any]):
    headers = authenticated_user_with_token["headers"]
    user_id = authenticated_user_with_token["user"]["id"]

    # Create a couple of keys first
    client.post("/api/v1/keys", json={"name": "Key 1"}, headers=headers)
    client.post("/api/v1/keys", json={"name": "Key 2", "scopes": ["test:scope"]}, headers=headers)

    response = client.get("/api/v1/keys", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    for key_info in data:
        assert "api_key" not in key_info # Full key should NOT be in list response
        assert "hashed_key" not in key_info
        assert "key_prefix" in key_info
        assert "name" in key_info
        assert "scopes" in key_info
        # Ensure all keys belong to the current user - this is implicitly tested by the endpoint logic
        # but could be verified if we query DB here with user_id

def test_list_api_keys_empty(client: TestClient, authenticated_user_with_token: Dict[str, Any]):
    # This test uses a new user who hasn't created keys yet
    # The fixture creates a new user each time, so this user won't have keys from previous tests in this file.
    headers = authenticated_user_with_token["headers"]
    response = client.get("/api/v1/keys", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0

def test_delete_api_key(client: TestClient, db_session: Session, authenticated_user_with_token: Dict[str, Any]):
    headers = authenticated_user_with_token["headers"]
    user_id = authenticated_user_with_token["user"]["id"]

    # Create a key to delete
    create_payload = {"name": "Key to Delete"}
    create_response = client.post("/api/v1/keys", json=create_payload, headers=headers)
    assert create_response.status_code == 201
    key_data_to_delete = create_response.json()
    key_prefix_to_delete = key_data_to_delete["key_prefix"]

    # Verify it's in DB before delete
    db_key = db_session.query(ApiKey).filter(ApiKey.key_prefix == key_prefix_to_delete, ApiKey.user_id == user_id).first()
    assert db_key is not None

    # Delete the key
    delete_response = client.delete(f"/api/v1/keys/{key_prefix_to_delete}", headers=headers)
    assert delete_response.status_code == 204

    # Verify it's gone from DB
    db_session.expire(db_key) # Expire to ensure fresh read if object was cached
    db_key_after_delete = db_session.query(ApiKey).filter(ApiKey.key_prefix == key_prefix_to_delete, ApiKey.user_id == user_id).first()
    assert db_key_after_delete is None

def test_delete_api_key_not_found(client: TestClient, authenticated_user_with_token: Dict[str, Any]):
    headers = authenticated_user_with_token["headers"]
    non_existent_prefix = "pfx_nonexist"

    delete_response = client.delete(f"/api/v1/keys/{non_existent_prefix}", headers=headers)
    assert delete_response.status_code == 404 # Or 403 if a distinction is made for "not found for this user"

# TODO: Test for deleting another user's key (would require more complex fixture setup)
# TODO: Test for key expiration if expires_at is implemented and checked on usage
# TODO: Test API key usage with the Bearer token auth (this will be part of A2A tests)
