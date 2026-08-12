"""CRM retrieval tools — read data from crm.json."""

from __future__ import annotations

import logging
from typing import Any

from app.services.data_loader import BaseDataTools

logger = logging.getLogger(__name__)


class CrmTools(BaseDataTools):
    """CRM-specific retrieval operations over local JSON data."""

    def __init__(self) -> None:
        super().__init__("crm.json")

    def get_all_customers_summary(self) -> list[dict[str, Any]]:
        """Return a pipeline-level summary for every customer."""
        result = []
        for rec in self._all_records():
            meta = rec.get("account_metadata", {})
            profile = rec.get("customer_profile", {})
            rm = rec.get("relationship_manager", {})
            pending_followups = sum(
                1
                for c in rec.get("conversation_history", [])
                if c.get("follow_up_required") and c.get("follow_up_date")
            )
            pending_suggestions = sum(
                1
                for s in rec.get("suggestions_provided", [])
                if s.get("status") in ("pending", "in_progress")
            )
            result.append(
                {
                    "customer_id": rec.get("customer_id"),
                    "name": profile.get("name"),
                    "segment": profile.get("segment"),
                    "relationship_manager": rm.get("name"),
                    "nps_score": meta.get("nps_score"),
                    "churn_risk": meta.get("churn_risk"),
                    "last_interaction_date": meta.get("last_interaction_date"),
                    "total_interactions_ytd": meta.get("total_interactions_ytd"),
                    "pending_followups": pending_followups,
                    "pending_suggestions": pending_suggestions,
                    "open_compliance_flags": len(rec.get("compliance_flags", [])),
                    "alerts": rec.get("alerts", []),
                }
            )
        logger.info("CRM customer summary list built", extra={"count": len(result)})
        return result

    def get_customer_full_profile(self, customer_id: str) -> dict[str, Any]:
        """Return demographics, account metadata, and RM info for one customer."""
        rec = self._find_customer(customer_id)
        return {
            "customer_id": rec.get("customer_id"),
            "customer_profile": rec.get("customer_profile", {}),
            "account_metadata": rec.get("account_metadata", {}),
            "relationship_manager": rec.get("relationship_manager", {}),
        }

    def get_interactions(
        self,
        customer_id: str,
        channel: str | None = None,
        sentiment: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Return conversation history and open service requests, with optional filters."""
        rec = self._find_customer(customer_id)
        convs: list[dict[str, Any]] = rec.get("conversation_history", [])

        if channel:
            convs = [c for c in convs if c.get("channel", "").lower() == channel.lower()]
        if sentiment:
            convs = [c for c in convs if c.get("sentiment", "").lower() == sentiment.lower()]
        if limit is not None and limit > 0:
            convs = convs[:limit]

        open_sr = [r for r in rec.get("service_requests", []) if r.get("status") != "resolved"]

        return {
            "customer_id": rec.get("customer_id"),
            "conversations": convs,
            "open_service_requests": open_sr,
        }

    def get_advisory_view(self, customer_id: str) -> dict[str, Any]:
        """Return suggestions, compliance flags, and active alerts."""
        rec = self._find_customer(customer_id)
        all_suggestions: list[dict[str, Any]] = rec.get("suggestions_provided", [])
        pending = [s for s in all_suggestions if s.get("status") in ("pending", "in_progress")]
        return {
            "customer_id": rec.get("customer_id"),
            "suggestions_provided": all_suggestions,
            "pending_suggestions": pending,
            "compliance_flags": rec.get("compliance_flags", []),
            "alerts": rec.get("alerts", []),
        }
