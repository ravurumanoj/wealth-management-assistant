"""Client (UI dropdown) request/response schemas."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AddClientRequest(BaseModel):
    """Request body for adding a demo client."""

    name: str = Field(..., min_length=1, max_length=100, description="Client display name.")
    portfolio_ids: List[str] = Field(
        default_factory=list, description="Portfolio identifiers to associate with the client."
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        """Trim surrounding whitespace and reject blank names."""
        value = value.strip()
        if not value:
            raise ValueError("Client name cannot be empty.")
        return value

    @field_validator("portfolio_ids")
    @classmethod
    def clean_portfolio_ids(cls, value: List[str]) -> List[str]:
        """Drop empty/whitespace-only ids."""
        return [p.strip() for p in value if p and p.strip()]


class Client(BaseModel):
    """A client entry in the UI dropdown list.

    Extra provider-specific fields (risk_profile, relationship_manager, …) are
    permitted so the same model covers both seeded and custom demo clients.
    """

    model_config = {"extra": "allow"}

    id: str = Field(..., description="Unique client identifier.")
    name: str = Field(..., description="Client display name.")
    segment: Optional[str] = Field(None, description="Client segment, e.g. HNI.")
    is_custom: Optional[bool] = Field(None, description="True for user-added demo clients.")
    portfolio_ids: Optional[List[str]] = Field(None, description="Associated portfolio ids.")


class ClientListResponse(BaseModel):
    """Envelope returned by the client-list endpoint."""

    clients: List[Client] = Field(default_factory=list, description="Available clients.")


class AddClientResponse(BaseModel):
    """Envelope returned after adding a demo client."""

    client: Client = Field(..., description="The newly created client.")
