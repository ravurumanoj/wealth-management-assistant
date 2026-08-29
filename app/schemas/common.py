"""Shared/generic response schemas used across multiple routers."""
from __future__ import annotations

from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    """Generic success message envelope."""

    message: str = Field(..., description="Human-readable status message.")


class DeletedResponse(BaseModel):
    """Returned by delete endpoints to confirm the removed resource id."""

    deleted: str = Field(..., description="Identifier of the deleted resource.")


class AppInfoResponse(BaseModel):
    """Dynamic app metadata shown in the chat UI header."""

    app_name: str = Field(..., description="Configured application name.")
    model: str = Field(..., description="Active LLM model name.")
    version: str = Field(..., description="Application version.")
