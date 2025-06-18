from datetime import datetime
from typing import Optional, List, Union # Added Union
from uuid import UUID
from pydantic import BaseModel, Field, validator, EmailStr

# Assuming A2ATaskStatus is in models.py as defined in a previous task
from app.models import A2ATaskStatus

# Existing Schemas (Memory, Category, App) - Keep them as they are
class MemoryBase(BaseModel):
    content: str
    metadata_: Optional[dict] = Field(default_factory=dict)

class MemoryCreate(MemoryBase):
    user_id: UUID
    app_id: UUID


class Category(BaseModel):
    name: str


class App(BaseModel):
    id: UUID
    name: str


class Memory(MemoryBase):
    id: UUID
    user_id: UUID
    app_id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    state: str
    categories: Optional[List[Category]] = None
    app: App

    class Config:
        from_attributes = True


# --- A2A Protocol Schemas ---
class A2ARPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Optional[dict] = None
    id: Union[str, int]

class A2ARPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int]

class A2ATaskCreateResult(BaseModel):
    task_id: str

class A2ATaskCreateResponse(A2ARPCResponse):
    result: A2ATaskCreateResult

class A2ATaskExecuteResponse(BaseModel): # This is not an RPC response, but a direct status after execute call
    task_id: str
    status: A2ATaskStatus # Using the enum from models
    message: Optional[str] = None
    # result: Optional[dict] = None # The PUT /execute endpoint can return the task result directly if desired
                                  # Or clients should use GET /tasks/{task_id} to fetch it.
                                  # For now, keeping it simple as per prompt.

    class Config:
        from_attributes = True # If status is directly from ORM object

class A2ATaskStatusResponse(BaseModel):
    task_id: str
    status: A2ATaskStatus # Using the enum from models
    method: str
    created_at: datetime
    updated_at: datetime
    params: Optional[dict] = None
    result: Optional[dict] = None

    class Config:
        from_attributes = True


# --- API Key Schemas ---
class ApiKeyBase(BaseModel):
    name: Optional[str] = None
    scopes: Optional[List[str]] = None
    expires_at: Optional[datetime] = None

class ApiKeyCreateRequest(ApiKeyBase):
    pass

class ApiKeyCreateResponse(BaseModel):
    api_key: str # The full, plain text API key. Only shown on creation.
    id: UUID
    name: Optional[str] = None
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime] = None
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True

class ApiKeyListResponseItem(BaseModel):
    id: UUID
    name: Optional[str] = None
    key_prefix: str
    scopes: List[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    metadata_: Optional[dict] = None
    state: Optional[str] = None


class MemoryResponse(BaseModel):
    id: UUID
    content: str
    created_at: int
    state: str
    app_id: UUID
    app_name: str
    categories: List[str]
    metadata_: Optional[dict] = None

    @validator('created_at', pre=True)
    def convert_to_epoch(cls, v):
        if isinstance(v, datetime):
            return int(v.timestamp())
        return v

class PaginatedMemoryResponse(BaseModel):
    items: List[MemoryResponse]
    total: int
    page: int
    size: int
    pages: int

# New User Schemas
class UserBase(BaseModel):
    email: EmailStr
    username: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel): # No longer inherits from UserBase to allow optional email/username
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str

    @validator('username', always=True)
    def check_username_or_email(cls, v, values):
        if not v and not values.get('email'):
            raise ValueError('Either username or email must be provided')
        return v

class UserResponse(UserBase): # Inherits username from UserBase now
    id: UUID # This is the internal UUID PK
    name: Optional[str] = None
    # No user_id field as it was removed from the model

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None # This will store the User.id (UUID) as a string in JWT 'sub'
    # In older versions or different setups, this might be 'username' or 'email'.
    # Using user.id (the UUID PK) is a common practice for 'sub'.
    # Renamed from task: sub: Optional[str] = None to user_id for clarity in our context
    # as we will store the user's User.id (PK) in the 'sub' claim.

    # Ensure email is also optional if username is provided, or handled by the validator logic
    @validator('email', always=True)
    def check_email_if_username_not_provided(cls, v, values):
        if not v and not values.get('username'):
            # This error is already raised by the username validator if both are missing.
            # This validator can be used if we want to enforce specific logic when email is present/absent
            # For now, the username validator covers the "at least one" case.
            pass
        if v and values.get('username'):
            # If specific logic is needed for when BOTH are provided, it can be added here.
            # For example, raise ValueError('Provide either username or email, not both')
            # However, current setup allows both, login logic will need to prioritize.
            pass
        return v

class ConfigEntry(BaseModel):
    key: str
    value: dict

    class Config:
        from_attributes = True
