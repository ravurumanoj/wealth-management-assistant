"""Entitlements service (P5.1) — the single access-control choke point.

Resolves the acting RM and decides which clients/portfolios they may see, so
entitlements are enforced BEFORE any data is retrieved
(FR-COM-001 / FR-COM-003 / FR-REL-010) and multiple matches are filtered to the
authorized set (FR-COM-002).

Backed by an optional ``data/entitlements.json``:

    {
      "default_all_access": true,
      "rms": {
        "RM-DEMO": {"clients": ["CUST-1001", "CUST-1002"], "portfolios": ["..."]}
      }
    }

When the file is absent, the RM is unknown, or ``default_all_access`` is true,
every client in the roster is authorized — so the demo works out of the box
while the enforcement mechanism stays real and pluggable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path as FilePath
from typing import Any, Dict, List, Optional, Set

from app.config import settings
from app.constants import DEFAULT_RM_ID, ENTITLEMENTS_DATA_FILE
from app.services.clients import load_clients
from app.utils.logger import logger

_ENTITLEMENTS_FILE = str(FilePath(__file__).resolve().parent.parent.parent / ENTITLEMENTS_DATA_FILE)


def _load_entitlements() -> Dict[str, Any]:
    """Load the entitlements config, or a permissive default when absent/invalid."""
    try:
        path = os.path.abspath(_ENTITLEMENTS_FILE)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.warning(f"entitlements: falling back to default_all_access ({e})")
    return {"default_all_access": True, "rms": {}}


def resolve_rm_id(metadata: Optional[Dict[str, Any]]) -> str:
    """Return the acting RM id from request metadata (demo default otherwise)."""
    return ((metadata or {}).get("rm_id") or DEFAULT_RM_ID).strip() or DEFAULT_RM_ID


def _all_client_ids() -> Set[str]:
    return {str(c.get("id")) for c in load_clients() if c.get("id")}


def authorized_client_ids(rm_id: str) -> Set[str]:
    """Return the set of client ids this RM may access."""
    cfg = _load_entitlements()
    if cfg.get("default_all_access", True):
        return _all_client_ids()
    rm = (cfg.get("rms") or {}).get(rm_id)
    if not rm:
        return set()   # explicit config with no entry → no access
    return {str(c) for c in (rm.get("clients") or [])}


def is_client_authorized(rm_id: str, client_id: Optional[str]) -> bool:
    """True when *rm_id* may access *client_id* (and a real client is selected)."""
    if not client_id or client_id == "unknown":
        return False
    if not settings.ENTITLEMENTS_ENABLED:
        return True
    return client_id in authorized_client_ids(rm_id)


def is_portfolio_authorized(rm_id: str, client_id: str, portfolio_id: str) -> bool:
    """True when *rm_id* may access *portfolio_id* for *client_id*."""
    if not settings.ENTITLEMENTS_ENABLED:
        return True
    if not is_client_authorized(rm_id, client_id):
        return False
    cfg = _load_entitlements()
    if cfg.get("default_all_access", True):
        return True
    rm = (cfg.get("rms") or {}).get(rm_id) or {}
    allowed = rm.get("portfolios")
    # No portfolio restriction configured → client-level authorization suffices.
    return True if not allowed else portfolio_id in {str(p) for p in allowed}


def filter_authorized_clients(
    rm_id: str, clients: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Filter a client roster down to the entries this RM may access."""
    if not settings.ENTITLEMENTS_ENABLED:
        return clients
    allowed = authorized_client_ids(rm_id)
    return [c for c in clients if str(c.get("id")) in allowed]
