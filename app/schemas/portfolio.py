"""Portfolio API response schemas.

Summary items are modelled field-by-field for precise validation. Detail
views model the top-level envelope returned by the tools; deeply-nested and
variable sub-objects (holdings, allocations, metrics) are kept flexible so the
schema documents the shape without breaking on live JSON data.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PortfolioSummaryItem(BaseModel):
    """One customer's RM book-of-business summary row."""

    customer_id: Optional[str] = None
    name: Optional[str] = None
    risk_profile: Optional[str] = None
    investment_horizon: Optional[str] = None
    relationship_manager: Optional[str] = None
    account_type: Optional[str] = None
    total_aum: Optional[float] = None
    currency: Optional[str] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    total_return_ytd_pct: Optional[float] = None
    benchmark_ytd_pct: Optional[float] = None
    alpha_pct: Optional[float] = None
    as_of_date: Optional[str] = None
    alert_count: int = 0
    alerts: List[Dict[str, Any]] = Field(default_factory=list)


class PortfolioSnapshot(BaseModel):
    """Holdings, allocation, and P&L for one customer."""

    customer_id: Optional[str] = None
    account_details: Dict[str, Any] = Field(default_factory=dict)
    customer_profile: Dict[str, Any] = Field(default_factory=dict)
    portfolio_summary: Dict[str, Any] = Field(default_factory=dict)
    asset_allocation: Dict[str, Any] = Field(default_factory=dict)
    holdings: List[Dict[str, Any]] = Field(default_factory=list)
    pnl_summary: Dict[str, Any] = Field(default_factory=dict)


class PerformanceView(BaseModel):
    """Performance metrics, exposures, and upcoming events for one customer."""

    customer_id: Optional[str] = None
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)
    sector_exposure: Dict[str, Any] = Field(default_factory=dict)
    geographic_exposure: Dict[str, Any] = Field(default_factory=dict)
    upcoming_events: List[Dict[str, Any]] = Field(default_factory=list)


class ComplianceView(BaseModel):
    """Line-of-credit, tax summary, and active alerts for one customer."""

    customer_id: Optional[str] = None
    line_of_credit: Optional[Dict[str, Any]] = None
    tax_summary: Dict[str, Any] = Field(default_factory=dict)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
