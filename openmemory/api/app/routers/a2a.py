from fastapi import APIRouter, HTTPException, Body, Depends, Request
from pydantic import BaseModel
from typing import Any, Dict

from app.models import ApiKey # Required for type hint if using the returned key
from app.routers.auth import verify_api_key_scope, SCOPES_A2A_DISPATCH
try:
    from app.main import limiter # Attempt to import limiter
except ImportError:
    class DummyLimiter: # Fallback if direct import from main is tricky
        def limit(self, *args, **kwargs):
            def decorator(func): return func
            return decorator
    limiter = DummyLimiter()

router = APIRouter(
    prefix="/a2a",
    tags=["a2a"],
)

# Static Agent Card
AGENT_CARD = {
    "name": "OpenMemory MCP",
    "description": "OpenMemory Memory Control Program. Manages and retrieves memories.",
    "version": "0.1.0",
    "api_endpoints": [
        {"method": "POST", "path": "/a2a/tasks/send", "description": "Send a task to the agent"},
    ],
    "documentation_url": "https://docs.openmemory.co/a2a" # Placeholder
}

@router.get("/.well-known/agent.json", response_model=Dict[str, Any])
async def get_agent_card():
    """
    Provides the agent card, describing the agent's capabilities.
    """
    return AGENT_CARD

class A2ATaskRequest(BaseModel):
    task_name: str
    payload: Dict[str, Any]
    # Could include fields like sender_agent_id, task_id, etc. in a real scenario

@router.post("/tasks/send")
@limiter.limit("60/minute")
async def handle_a2a_task(
    request: Request, # Added for rate limiter
    task_request: A2ATaskRequest = Body(...),
    # Protect this endpoint: Only keys with "a2a:dispatch" scope can send tasks.
    # The 'requesting_api_key' object can be used if needed (e.g. to identify the caller)
    requesting_api_key: ApiKey = Depends(verify_api_key_scope([SCOPES_A2A_DISPATCH]))
):
    """
    Handles incoming A2A tasks.
    Currently, it's a placeholder and doesn't process tasks.
    """
    # In a real implementation, this would:
    # 1. Validate the task_name and payload.
    # 2. Authenticate/authorize the sending agent (e.g., via API key, mutual TLS).
    # 3. Route the task to an appropriate handler based on task_name.
    # 4. Execute the task (potentially asynchronously).
    # 5. Return a meaningful response (e.g., task accepted, task completed, error).

    print(f"Received A2A task: {task_request.task_name}")
    print(f"Payload: {task_request.payload}")

    # Placeholder response
    if task_request.task_name == "example.greet":
        return {"status": "success", "message": "Greeting received!", "data": task_request.payload}

    # For now, just acknowledge receipt for any other task.
    return {"status": "success", "message": f"Task '{task_request.task_name}' received and acknowledged."}

# Example of how another agent might call this:
# import requests
# response = requests.post(
#     "http://localhost:8765/a2a/tasks/send", # Assuming OpenMemory runs on port 8765
#     json={
#         "task_name": "example.store_memory",
#         "payload": {"content": "This is a memory from another agent."}
#     },
#     headers={"X-API-Key": "some_api_key_if_required"} # If auth is implemented
# )
# print(response.json())
