import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Tuple
from uuid import uuid4
import secrets # For generating task IDs if needed, though backend does it

from app.main import app
from app.models import User, ApiKey, A2ATask, A2ATaskStatus
from app.schemas import A2ARPCRequest, A2ATaskCreateResponse, A2ATaskStatusResponse, A2ATaskExecuteResponse
from app.database import Base, engine # For potential table setup/teardown if not handled by higher level fixtures

A2A_DISPATCH_SCOPE = "a2a:dispatch" # From a2a.py (or central config)

@pytest.fixture(scope="function")
def a2a_user_with_bearer_token(client: TestClient, db_session: Session) -> Dict[str, Any]:
    # 1. Create User
    rand_id = uuid4().hex[:8]
    user_payload = {
        "username": f"a2auser_{rand_id}",
        "email": f"a2auser_{rand_id}@example.com",
        "password": "testpassword123"
    }
    reg_response = client.post("/auth/register", json=user_payload)
    assert reg_response.status_code == 201
    user_info_from_reg = reg_response.json() # Contains id, username, email

    # 2. Login User to get JWT token
    login_payload = {"username": user_payload["username"], "password": user_payload["password"]}
    login_response = client.post("/auth/login", json=login_payload)
    assert login_response.status_code == 200
    jwt_token_data = login_response.json()
    user_jwt_headers = {"Authorization": f"Bearer {jwt_token_data['access_token']}"}

    # 3. Create API Key for this user with a2a:dispatch scope
    key_create_payload = {
        "name": "A2A Test Key",
        "scopes": [A2A_DISPATCH_SCOPE]
    }
    key_response = client.post("/api/v1/keys", json=key_create_payload, headers=user_jwt_headers)
    assert key_response.status_code == 201
    key_data = key_response.json()
    plain_api_key = key_data["api_key"] # This is the Bearer token for A2A

    return {
        "bearer_token": plain_api_key,
        "user": user_info_from_reg, # Contains id, username, email
        "headers": {"Authorization": f"Bearer {plain_api_key}"} # Convenience for A2A calls
    }

def test_get_agent_card(client: TestClient):
    response = client.get("/a2a/agent-card")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "OpenMemory MCP"
    assert "api_endpoints" in data
    assert "auth" in data
    assert data["auth"]["type"] == "bearer"
    assert "skills" in data
    assert "add_memory" in data["skills"]

def test_create_a2a_task_success(client: TestClient, db_session: Session, a2a_user_with_bearer_token: Dict[str, Any]):
    headers = a2a_user_with_bearer_token["headers"]
    user_id = a2a_user_with_bearer_token["user"]["id"]

    rpc_request_id = uuid4().hex[:6]
    task_payload = A2ARPCRequest(
        method="add_memory",
        params={"content": "Test memory for A2A task"},
        id=rpc_request_id
    )

    response = client.post("/a2a/tasks", json=task_payload.model_dump(), headers=headers)
    assert response.status_code == 201
    data = response.json() # Should be A2ATaskCreateResponse
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == rpc_request_id
    assert "result" in data
    assert "task_id" in data["result"]
    created_task_id = data["result"]["task_id"]

    db_task = db_session.query(A2ATask).filter(A2ATask.task_id == created_task_id).first()
    assert db_task is not None
    assert db_task.user_id == user_id
    assert db_task.method == "add_memory"
    assert db_task.status == A2ATaskStatus.SUBMITTED
    assert db_task.params == {"content": "Test memory for A2A task"}

def test_create_a2a_task_invalid_token(client: TestClient):
    rpc_request_id = uuid4().hex[:6]
    task_payload = A2ARPCRequest(
        method="add_memory",
        params={"content": "Test memory"},
        id=rpc_request_id
    )
    invalid_headers = {"Authorization": "Bearer invalidbearertoken"}
    response = client.post("/a2a/tasks", json=task_payload.model_dump(), headers=invalid_headers)
    assert response.status_code == 401 # Unauthorized due to invalid API key

# TODO: Test create_a2a_task with key missing "a2a:dispatch" scope (requires more complex fixture)

def test_execute_a2a_task_success(client: TestClient, db_session: Session, a2a_user_with_bearer_token: Dict[str, Any]):
    headers = a2a_user_with_bearer_token["headers"]

    # 1. Create a task first
    rpc_request_id = uuid4().hex[:6]
    create_task_payload = A2ARPCRequest(method="add_memory", params={"detail": "execute test"}, id=rpc_request_id)
    create_response = client.post("/a2a/tasks", json=create_task_payload.model_dump(), headers=headers)
    assert create_response.status_code == 201
    task_id = create_response.json()["result"]["task_id"]

    # 2. Execute the task
    execute_response = client.put(f"/a2a/tasks/{task_id}/execute", headers=headers)
    assert execute_response.status_code == 200
    data = execute_response.json() # Should be A2ATaskExecuteResponse
    assert data["task_id"] == task_id
    assert data["status"] == A2ATaskStatus.COMPLETED.value # Or FAILED if method not implemented in simulation

    db_task = db_session.query(A2ATask).filter(A2ATask.task_id == task_id).first()
    assert db_task is not None
    assert db_task.status == A2ATaskStatus.COMPLETED # Or FAILED
    assert db_task.result is not None

def test_get_a2a_task_status_success(client: TestClient, db_session: Session, a2a_user_with_bearer_token: Dict[str, Any]):
    headers = a2a_user_with_bearer_token["headers"]
    user_id = a2a_user_with_bearer_token["user"]["id"]

    # 1. Create and execute a task
    rpc_request_id = uuid4().hex[:6]
    task_method = "search_memory"
    task_params = {"query": "A2A status test"}
    create_task_payload = A2ARPCRequest(method=task_method, params=task_params, id=rpc_request_id)
    create_response = client.post("/a2a/tasks", json=create_task_payload.model_dump(), headers=headers)
    task_id = create_response.json()["result"]["task_id"]
    client.put(f"/a2a/tasks/{task_id}/execute", headers=headers) # Execute it

    # 2. Get task status
    status_response = client.get(f"/a2a/tasks/{task_id}", headers=headers)
    assert status_response.status_code == 200
    data = status_response.json() # Should be A2ATaskStatusResponse
    assert data["task_id"] == task_id
    assert data["status"] == A2ATaskStatus.COMPLETED.value # Or FAILED
    assert data["method"] == task_method
    assert data["params"] == task_params
    assert data["result"] is not None

    db_task = db_session.query(A2ATask).filter(A2ATask.task_id == task_id).first()
    assert db_task is not None
    assert db_task.user_id == user_id


def test_execute_task_not_found(client: TestClient, a2a_user_with_bearer_token: Dict[str, Any]):
    headers = a2a_user_with_bearer_token["headers"]
    response = client.put("/a2a/tasks/task_nonexistent/execute", headers=headers)
    assert response.status_code == 404

def test_get_task_status_not_found(client: TestClient, a2a_user_with_bearer_token: Dict[str, Any]):
    headers = a2a_user_with_bearer_token["headers"]
    response = client.get("/a2a/tasks/task_nonexistent", headers=headers)
    assert response.status_code == 404

# TODO: Test executing task not in SUBMITTED state
# TODO: Test accessing/executing task belonging to another user (would require more complex fixture)
