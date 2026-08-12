"""Four LangChain tools wrapping the portfolio API operations.

These are the same 4 operations exposed by the /api/v1/portfolio routes,
surfaced as @tool callables so the portfolio_insights agent can use
LLM-driven tool calling.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from app.services.portfolio_tools import PortfolioTools

_portfolio = PortfolioTools()


@tool
def portfolio_list_summary() -> list[dict[str, Any]]:
    """Return an RM book-of-business overview for ALL customers.

    Use this when the user asks about multiple customers, the full book,
    or a general portfolio overview without specifying a single customer.
    Returns: list of lightweight summary records (AUM, YTD return, alpha, alerts).
    """
    return _portfolio.get_all_portfolios_summary()


@tool
def portfolio_snapshot(customer_id: str) -> dict[str, Any]:
    """Return holdings, asset allocation, and P&L for ONE customer.

    Use this for questions about a specific customer's holdings, positions,
    asset mix, or profit-and-loss statement.

    Args:
        customer_id: Customer identifier, e.g. CUST-1001.
    """
    return _portfolio.get_portfolio_snapshot(customer_id)


@tool
def portfolio_performance(customer_id: str) -> dict[str, Any]:
    """Return performance metrics, sector/geo exposure, and upcoming events for ONE customer.

    Use this for questions about returns (1M/3M/YTD/1Y), benchmark comparison,
    Sharpe ratio, alpha/beta, sector weights, geographic breakdown, or event calendar.

    Args:
        customer_id: Customer identifier, e.g. CUST-1001.
    """
    return _portfolio.get_performance_view(customer_id)


@tool
def portfolio_compliance(customer_id: str) -> dict[str, Any]:
    """Return line-of-credit details, tax summary, and active alerts for ONE customer.

    Use this for questions about the LOC facility, STCG/LTCG tax exposure,
    tax-loss harvesting, TDS, or outstanding compliance alerts.

    Args:
        customer_id: Customer identifier, e.g. CUST-1001.
    """
    return _portfolio.get_compliance_view(customer_id)


# Exported list consumed by PortfolioInsightsAgent
PORTFOLIO_TOOLS = [
    portfolio_list_summary,
    portfolio_snapshot,
    portfolio_performance,
    portfolio_compliance,
]
