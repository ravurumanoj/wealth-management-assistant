"""CRM API response schemas.

Summary items are modelled field-by-field; detail views model the top-level
envelope and keep deeply-nested, variable sub-objects flexible.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CrmSummaryItem(BaseModel):
    """One customer's CRM pipeline summary row."""

    customer_id: Optional[str] = None
    name: Optional[str] = None
    segment: Optional[str] = None
    relationship_manager: Optional[str] = None
    nps_score: Optional[int] = None
    churn_risk: Optional[str] = None
    last_interaction_date: Optional[str] = None
    total_interactions_ytd: Optional[int] = None
    pending_followups: int = 0
    pending_suggestions: int = 0
    open_compliance_flags: int = 0
    # alerts are stored as plain strings in crm.json; accept str or object.
    alerts: List[Any] = Field(default_factory=list)


class CustomerProfileView(BaseModel):
    """Demographics, account metadata, and RM info for one customer."""

    customer_id: Optional[str] = None
    customer_profile: Dict[str, Any] = Field(default_factory=dict)
    account_metadata: Dict[str, Any] = Field(default_factory=dict)
    relationship_manager: Dict[str, Any] = Field(default_factory=dict)


class InteractionsView(BaseModel):
    """Conversation history and open service requests for one customer."""

    customer_id: Optional[str] = None
    conversations: List[Dict[str, Any]] = Field(default_factory=list)
    open_service_requests: List[Dict[str, Any]] = Field(default_factory=list)


class AdvisoryView(BaseModel):
    """Suggestions, compliance flags, and active alerts for one customer."""

    customer_id: Optional[str] = None
    suggestions_provided: List[Dict[str, Any]] = Field(default_factory=list)
    pending_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    compliance_flags: List[Dict[str, Any]] = Field(default_factory=list)
    # alerts are stored as plain strings in crm.json; accept str or object.
    alerts: List[Any] = Field(default_factory=list)
