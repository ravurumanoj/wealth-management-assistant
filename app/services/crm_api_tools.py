"""Four LangChain tools wrapping the CRM API operations.

These are the same 4 operations exposed by the /api/v1/crm routes, surfaced as
@tool callables so the relationship_intelligence agent can use LLM-driven tool
calling when no external MCP CRM server is configured.
"""

from __future__ import annotations

from typing import Any, Optional

from langchain_core.tools import tool

from app.services.crm_tools import CrmTools

_crm = CrmTools()


@tool
def crm_list_summary() -> list[dict[str, Any]]:
    """Return an RM pipeline overview for ALL customers.

    Use this when the user asks about multiple customers, the full client book,
    or a general CRM overview without specifying a single customer.
    Returns: list of summary rows (NPS, churn risk, pending follow-ups, alerts).
    """
    return _crm.get_all_customers_summary()


@tool
def crm_customer_profile(customer_id: str) -> dict[str, Any]:
    """Return demographics, account metadata, and RM info for ONE customer.

    Use this for questions about who the client is, KYC status, segment,
    contact preferences, lifetime value, or relationship manager details.

    Args:
        customer_id: Customer identifier, e.g. CUST-1001.
    """
    return _crm.get_customer_full_profile(customer_id)


@tool
def crm_interactions(
    customer_id: str,
    channel: Optional[str] = None,
    sentiment: Optional[str] = None,
    limit: Optional[int] = None,
) -> dict[str, Any]:
    """Return conversation history and open service requests for ONE customer.

    Use this for questions about recent interactions, meetings, calls, emails,
    client sentiment, or open service requests / tickets.

    Args:
        customer_id: Customer identifier, e.g. CUST-1001.
        channel: Optional filter — phone | email | in_person | video_call | app_chat.
        sentiment: Optional filter — positive | neutral | negative.
        limit: Optional — return only the most recent N conversations.
    """
    return _crm.get_interactions(customer_id, channel=channel, sentiment=sentiment, limit=limit)


@tool
def crm_advisory(customer_id: str) -> dict[str, Any]:
    """Return suggestions, compliance flags, and active alerts for ONE customer.

    Use this for questions about next best actions, advisory suggestions,
    compliance flags, or outstanding alerts / follow-ups for a client.

    Args:
        customer_id: Customer identifier, e.g. CUST-1001.
    """
    return _crm.get_advisory_view(customer_id)


# Ordered list consumed by the relationship_intelligence agent as a local fallback.
CRM_TOOLS = [crm_list_summary, crm_customer_profile, crm_interactions, crm_advisory]
