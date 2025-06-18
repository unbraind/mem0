from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Any, Dict

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
async def handle_a2a_task(task_request: A2ATaskRequest = Body(...)):
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
