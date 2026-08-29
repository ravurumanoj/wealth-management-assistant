"""CRM API routes — read-only endpoints backed by crm.json.

Route map
---------
GET /crm/                             All customers RM pipeline summary
GET /crm/{customer_id}                Demographics + account metadata + RM info
GET /crm/{customer_id}/interactions   Conversations (filterable) + open tickets
GET /crm/{customer_id}/advisory       Suggestions + compliance flags + alerts
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from app.errors import DataAccessError
from app.schemas.crm import (
    AdvisoryView,
    CrmSummaryItem,
    CustomerProfileView,
    InteractionsView,
)
from app.services.crm_tools import CrmTools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["CRM"])
_tools = CrmTools()


def _raise_404_if_not_found(exc: DataAccessError, customer_id: str) -> None:
    if "No record found" in exc.message:
        raise HTTPException(
            status_code=404,
            detail=f"Customer '{customer_id}' not found in the CRM database.",
        ) from exc
    raise exc


@router.get(
    "/",
    summary="All customers — RM pipeline summary",
    response_model=list[CrmSummaryItem],
)
def list_customers_summary() -> list[dict[str, Any]]:
    """Return an RM pipeline overview for all customers."""
    logger.info("CRM customer summary list requested")
    return _tools.get_all_customers_summary()


@router.get(
    "/{customer_id}",
    summary="Customer full profile",
    response_model=CustomerProfileView,
)
def get_customer_full_profile(customer_id: str) -> dict[str, Any]:
    """Return demographics, account metadata, and RM info for one customer."""
    logger.info("Customer full profile requested", extra={"customer_id": customer_id})
    try:
        return _tools.get_customer_full_profile(customer_id)
    except DataAccessError as exc:
        _raise_404_if_not_found(exc, customer_id)


@router.get(
    "/{customer_id}/interactions",
    summary="Interactions — conversations + open service requests",
    response_model=InteractionsView,
)
def get_interactions(
    customer_id: str,
    channel: Annotated[
        str | None,
        Query(description="Filter by channel: phone | email | in_person | video_call | app_chat"),
    ] = None,
    sentiment: Annotated[
        str | None,
        Query(description="Filter by sentiment: positive | neutral | negative"),
    ] = None,
    limit: Annotated[
        int | None,
        Query(ge=1, le=50, description="Return only the most recent N conversations."),
    ] = None,
) -> dict[str, Any]:
    """Return conversation history and open service requests, with optional filters."""
    logger.info(
        "Interactions requested",
        extra={"customer_id": customer_id, "channel": channel, "sentiment": sentiment, "limit": limit},
    )
    try:
        return _tools.get_interactions(customer_id, channel=channel, sentiment=sentiment, limit=limit)
    except DataAccessError as exc:
        _raise_404_if_not_found(exc, customer_id)


@router.get(
    "/{customer_id}/advisory",
    summary="Advisory view — suggestions, compliance, alerts",
    response_model=AdvisoryView,
)
def get_advisory_view(customer_id: str) -> dict[str, Any]:
    """Return suggestions, compliance flags, and active alerts."""
    logger.info("Advisory view requested", extra={"customer_id": customer_id})
    try:
        return _tools.get_advisory_view(customer_id)
    except DataAccessError as exc:
        _raise_404_if_not_found(exc, customer_id)
