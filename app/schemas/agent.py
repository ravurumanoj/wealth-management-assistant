
import re
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional

# Validation constants mirror the original helper logic in app/utils/helpers.py
_SESSION_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
_CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]')
_MAX_SESSION_ID_LENGTH = 100
_MAX_MESSAGE_LENGTH = 5000


class ChatRequest(BaseModel):
    message: str = Field(..., description="User input message")
    session_id: str = Field(..., description="Unique session identifier")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context/metadata")

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, value: str) -> str:
        """Session ID must be alphanumeric with optional hyphens/underscores and <= 100 chars."""
        if not value or len(value) > _MAX_SESSION_ID_LENGTH or not _SESSION_ID_PATTERN.match(value):
            raise ValueError(
                "Invalid session ID format. Use alphanumeric characters, hyphens, or underscores."
            )
        return value

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, value: str) -> str:
        """Truncate to max length, strip control characters/whitespace, and reject empties."""
        text = value[:_MAX_MESSAGE_LENGTH]
        text = _CONTROL_CHAR_PATTERN.sub('', text)
        text = text.strip()
        if not text:
            raise ValueError("Message cannot be empty")
        return text

class ChatResponse(BaseModel):
    session_id: str
    response: str
    agent_used: Optional[str] = None
    intermediate_steps: Optional[List[Dict[str, Any]]] = None

class SessionInfo(BaseModel):
    session_id: str
    client_id: Optional[str] = "unknown"
    last_updated: str
    history_count: int

