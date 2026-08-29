
import re
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional

from app.constants import (
    CONTROL_CHAR_REGEX,
    MAX_MESSAGE_LENGTH,
    MAX_SESSION_ID_LENGTH,
    SESSION_ID_REGEX,
)

_SESSION_ID_PATTERN = re.compile(SESSION_ID_REGEX)
_CONTROL_CHAR_PATTERN = re.compile(CONTROL_CHAR_REGEX)
_MAX_SESSION_ID_LENGTH = MAX_SESSION_ID_LENGTH
_MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH


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


class ChatMessage(BaseModel):
    """A single stored message within a session's history."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'.")
    content: str = Field(..., description="Message text.")
    timestamp: Optional[str] = Field(None, description="ISO-8601 message timestamp.")


class SessionHistoryResponse(BaseModel):
    """Full chat history for one session."""

    session_id: str = Field(..., description="Session identifier.")
    history: List[ChatMessage] = Field(
        default_factory=list, description="Messages in chronological order."
    )

