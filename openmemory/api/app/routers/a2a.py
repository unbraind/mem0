import uuid
import hashlib # Should be in auth.py, but if used directly for other hashing, keep.
import secrets
from typing import List, Optional, Tuple, Union, Any, Dict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Body, Path, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, ApiKey, A2ATask, A2ATaskStatus # Added A2ATask, A2ATaskStatus
from app import schemas # Pydantic schemas
from app.routers.auth import verify_bearer_api_key_scope # New Bearer auth dependency

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

# Scope constant for A2A operations
SCOPES_A2A_DISPATCH = "a2a:dispatch" # This scope allows creating and managing A2A tasks

router = APIRouter(
    prefix="/a2a",
    tags=["A2A Protocol"], # Updated tag
)

# Agent Card as per new specification
AGENT_CARD = {
    "name": "OpenMemory MCP",
    "description": "OpenMemory Memory Control Program. Manages and retrieves memories via A2A protocol.",
    "version": "0.2.0", # Version bump for new A2A spec
    "api_endpoints": [ # These should reflect the new JSON-RPC style task endpoints
        {"method": "POST", "path": "/a2a/tasks", "description": "Submit a new task (e.g., add_memory, search_memory)."},
        {"method": "PUT", "path": "/a2a/tasks/{task_id}/execute", "description": "Trigger execution of a submitted task."},
        {"method": "GET", "path": "/a2a/tasks/{task_id}", "description": "Get the status and result of a task."}
    ],
    "auth": {
        "type": "bearer", # Specify Bearer token authentication
        "documentation_url": "/docs" # Point to API docs for auth details
    },
    "skills": [ # List of supported methods/skills
        "add_memory",
        "search_memory"
        # Other skills can be added here
    ],
    "documentation_url": "https://docs.openmemory.co/a2a" # Placeholder
}

@router.get("/agent-card", response_model=Dict[str, Any])
async def get_agent_card_endpoint(): # Renamed function for clarity
    """
    Provides the agent card, describing the agent's capabilities,
    authentication, and available skills according to the A2A JSON-RPC spec.
    """
    return AGENT_CARD

# Placeholder for the rest of the A2A endpoints (POST /tasks, PUT /tasks/{task_id}/execute, GET /tasks/{task_id})
# These will be added in subsequent steps.

@router.post("/tasks", response_model=schemas.A2ATaskCreateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute") # Example rate limit
async def submit_a2a_task(
    request: Request, # For limiter
    rpc_request: schemas.A2ARPCRequest,
    db: Session = Depends(get_db),
    user_and_scopes: Tuple[User, List[str]] = Depends(verify_bearer_api_key_scope([SCOPES_A2A_DISPATCH]))
):
    current_user, _ = user_and_scopes

    # Validate method (optional, could be done during execution)
    # For now, we accept any method string.
    # if rpc_request.method not in AGENT_CARD.get("skills", []):
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail=f"Method '{rpc_request.method}' not supported by this agent."
    #     )

    task_id = f"task_{secrets.token_hex(16)}"

    new_task = A2ATask(
        task_id=task_id,
        user_id=current_user.id,
        status=A2ATaskStatus.SUBMITTED,
        method=rpc_request.method,
        params=rpc_request.params
        # result is initially null
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return schemas.A2ATaskCreateResponse(
        id=rpc_request.id, # Echo back the original RPC request ID
        result=schemas.A2ATaskCreateResult(task_id=new_task.task_id)
    )

@router.put("/tasks/{task_id}/execute", response_model=schemas.A2ATaskExecuteResponse)
@limiter.limit("30/minute") # Example rate limit, potentially lower than task creation
async def execute_a2a_task(
    request: Request, # For limiter
    task_id: str = Path(..., title="The ID of the task to execute"),
    db: Session = Depends(get_db),
    user_and_scopes: Tuple[User, List[str]] = Depends(verify_bearer_api_key_scope([SCOPES_A2A_DISPATCH]))
):
    current_user, _ = user_and_scopes

    task = db.query(A2ATask).filter(A2ATask.task_id == task_id).first()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    if task.user_id != current_user.id:
        # This check ensures users can only execute their own tasks
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to execute this task.")

    if task.status != A2ATaskStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task cannot be executed. Current status: {task.status.value}"
        )

    # Update status to WORKING
    task.status = A2ATaskStatus.WORKING
    task.updated_at = datetime.utcnow() # Manually update updated_at
    db.add(task)
    db.commit()
    db.refresh(task)

    # --- Simulate task execution ---
    # In a real scenario, this would involve calling the actual method/tool
    # For example, if task.method == "add_memory": mem0.add(...)
    # Or if task.method == "search_memory": mem0.search(...)
    simulated_result = {}
    message = "Task execution simulated."
    try:
        if task.method == "add_memory":
            # Simulate adding memory, e.g., log params
            print(f"Simulating add_memory with params: {task.params}")
            simulated_result = {"status": "memory_added", "details": "Simulated add_memory successful."}
            task.status = A2ATaskStatus.COMPLETED
        elif task.method == "search_memory":
            # Simulate searching memory
            print(f"Simulating search_memory with params: {task.params}")
            simulated_result = {"results": [{"content": "simulated memory result", "score": 0.9}]}
            task.status = A2ATaskStatus.COMPLETED
        else:
            message = f"Method '{task.method}' is recognized but not implemented in this simulation."
            simulated_result = {"error": "method_not_implemented_simulation"}
            task.status = A2ATaskStatus.FAILED # Or keep as WORKING if it's a long process
                                               # For simulation, we'll mark as FAILED if not one of the above.
    except Exception as e:
        print(f"Error during simulated execution of task {task.id} ({task.method}): {e}")
        simulated_result = {"error": "simulation_exception", "detail": str(e)}
        task.status = A2ATaskStatus.FAILED
        message = "Task execution failed during simulation."

    task.result = simulated_result
    task.updated_at = datetime.utcnow() # Manually update updated_at
    db.add(task)
    db.commit()
    db.refresh(task)

    return schemas.A2ATaskExecuteResponse(
        task_id=task.task_id,
        status=task.status, # This will be COMPLETED or FAILED from simulation
        message=message
    )

@router.get("/tasks/{task_id}", response_model=schemas.A2ATaskStatusResponse)
@limiter.limit("60/minute") # Example rate limit
async def get_a2a_task_status(
    request: Request, # For limiter
    task_id: str = Path(..., title="The ID of the task to retrieve"),
    db: Session = Depends(get_db),
    user_and_scopes: Tuple[User, List[str]] = Depends(verify_bearer_api_key_scope([SCOPES_A2A_DISPATCH]))
):
    current_user, _ = user_and_scopes

    task = db.query(A2ATask).filter(A2ATask.task_id == task_id).first()

    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

    if task.user_id != current_user.id:
        # This check ensures users can only view their own tasks
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this task.")

    return schemas.A2ATaskStatusResponse(
        task_id=task.task_id,
        status=task.status,
        method=task.method,
        created_at=task.created_at,
        updated_at=task.updated_at,
        params=task.params,
        result=task.result
    )
