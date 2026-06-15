
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ChatRequest(BaseModel):
    message: str = Field(..., description="User input message")
    session_id: str = Field(..., description="Unique session identifier")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context/metadata")

class ChatResponse(BaseModel):
    session_id: str
    response: str
    agent_used: Optional[str] = None
    intermediate_steps: Optional[List[Dict[str, Any]]] = None

class SessionInfo(BaseModel):
    session_id: str
    last_updated: str
    history_count: int

