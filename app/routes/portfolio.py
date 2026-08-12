"""Portfolio API routes — read-only endpoints backed by portfolio.json.

Route map
---------
GET /portfolio/                           All portfolios RM summary
GET /portfolio/{customer_id}              Holdings + asset allocation + P&L
GET /portfolio/{customer_id}/performance  Metrics + sector/geo exposure + events
GET /portfolio/{customer_id}/compliance   LOC + tax summary + alerts
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from app.errors import DataAccessError
from app.services.portfolio_tools import PortfolioTools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])
_tools = PortfolioTools()


def _raise_404_if_not_found(exc: DataAccessError, customer_id: str) -> None:
    if "No record found" in exc.message:
        raise HTTPException(
            status_code=404,
            detail=f"Customer '{customer_id}' not found in the portfolio database.",
        ) from exc
    raise exc


@router.get("/", summary="All portfolios — RM summary")
def list_portfolios_summary() -> list[dict[str, Any]]:
    """Return an RM book-of-business overview for all customers."""
    logger.info("Portfolio summary list requested")
    return _tools.get_all_portfolios_summary()


@router.get("/{customer_id}", summary="Portfolio snapshot — holdings, allocation, P&L")
def get_portfolio_snapshot(customer_id: str) -> dict[str, Any]:
    """Return holdings, asset allocation, and P&L for one customer."""
    logger.info("Portfolio snapshot requested", extra={"customer_id": customer_id})
    try:
        return _tools.get_portfolio_snapshot(customer_id)
    except DataAccessError as exc:
        _raise_404_if_not_found(exc, customer_id)


@router.get("/{customer_id}/performance", summary="Performance view — metrics, exposure, events")
def get_performance_view(customer_id: str) -> dict[str, Any]:
    """Return performance metrics, sector/geo exposure, and upcoming events."""
    logger.info("Performance view requested", extra={"customer_id": customer_id})
    try:
        return _tools.get_performance_view(customer_id)
    except DataAccessError as exc:
        _raise_404_if_not_found(exc, customer_id)


@router.get("/{customer_id}/compliance", summary="Compliance view — LOC, tax, alerts")
def get_compliance_view(customer_id: str) -> dict[str, Any]:
    """Return LOC details, tax summary, and active alerts."""
    logger.info("Compliance view requested", extra={"customer_id": customer_id})
    try:
        return _tools.get_compliance_view(customer_id)
    except DataAccessError as exc:
        _raise_404_if_not_found(exc, customer_id)
