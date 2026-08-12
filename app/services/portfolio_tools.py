"""Portfolio retrieval tools — read data from portfolio.json."""

from __future__ import annotations

import logging
from typing import Any

from app.services.data_loader import BaseDataTools

logger = logging.getLogger(__name__)


class PortfolioTools(BaseDataTools):
    """Portfolio-specific retrieval operations over local JSON data."""

    def __init__(self) -> None:
        super().__init__("portfolio.json")

    def get_all_portfolios_summary(self) -> list[dict[str, Any]]:
        """Return a high-level RM book-of-business summary for every customer."""
        result = []
        for rec in self._all_records():
            profile = rec.get("customer_profile", {})
            acc = rec.get("account_details", {})
            summary = rec.get("portfolio_summary", {})
            metrics = rec.get("performance_metrics", {})
            result.append(
                {
                    "customer_id": rec.get("customer_id"),
                    "name": profile.get("name"),
                    "risk_profile": profile.get("risk_profile"),
                    "investment_horizon": profile.get("investment_horizon"),
                    "relationship_manager": acc.get("relationship_manager"),
                    "account_type": acc.get("account_type"),
                    "total_aum": summary.get("total_aum"),
                    "currency": summary.get("currency"),
                    "unrealized_pnl": summary.get("unrealized_pnl"),
                    "unrealized_pnl_pct": summary.get("unrealized_pnl_pct"),
                    "total_return_ytd_pct": summary.get("total_return_ytd_pct"),
                    "benchmark_ytd_pct": metrics.get("benchmark_ytd_pct"),
                    "alpha_pct": metrics.get("alpha_pct"),
                    "as_of_date": summary.get("as_of_date"),
                    "alert_count": len(rec.get("alerts", [])),
                    "alerts": rec.get("alerts", []),
                }
            )
        logger.info("Portfolio summary list built", extra={"count": len(result)})
        return result

    def get_portfolio_snapshot(self, customer_id: str) -> dict[str, Any]:
        """Return holdings, asset allocation, and P&L for one customer."""
        rec = self._find_customer(customer_id)
        return {
            "customer_id": rec.get("customer_id"),
            "account_details": rec.get("account_details", {}),
            "customer_profile": rec.get("customer_profile", {}),
            "portfolio_summary": rec.get("portfolio_summary", {}),
            "asset_allocation": rec.get("asset_allocation", {}),
            "holdings": rec.get("holdings", []),
            "pnl_summary": rec.get("pnl_summary", {}),
        }

    def get_performance_view(self, customer_id: str) -> dict[str, Any]:
        """Return performance metrics, sector/geo exposure, and upcoming events."""
        rec = self._find_customer(customer_id)
        return {
            "customer_id": rec.get("customer_id"),
            "performance_metrics": rec.get("performance_metrics", {}),
            "sector_exposure": rec.get("sector_exposure", {}),
            "geographic_exposure": rec.get("geographic_exposure", {}),
            "upcoming_events": rec.get("upcoming_events", []),
        }

    def get_compliance_view(self, customer_id: str) -> dict[str, Any]:
        """Return LOC details, tax summary, and active alerts."""
        rec = self._find_customer(customer_id)
        return {
            "customer_id": rec.get("customer_id"),
            "line_of_credit": rec.get("line_of_credit"),
            "tax_summary": rec.get("tax_summary", {}),
            "alerts": rec.get("alerts", []),
        }
