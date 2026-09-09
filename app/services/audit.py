"""Audit logging service (P5.2) — FR-COM-011.

Writes one PII-redacted JSON line per turn (and per governance denial/block) to a
dedicated rotating audit log, independent of the application log. Never raises —
auditing must not break request handling.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, List, Optional

from app.config import settings
from app.constants import (
    AUDIT_LOG_FILE,
    AUDIT_LOGGER_NAME,
    AUDIT_QUERY_MAX_LEN,
    AUDIT_RESPONSE_MAX_LEN,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
)
from app.services.guardrails import redact_pii

_audit_logger: Optional[logging.Logger] = None


def _get_audit_logger() -> Optional[logging.Logger]:
    """Lazily create the dedicated audit logger (JSON lines, rotating file)."""
    global _audit_logger
    if _audit_logger is not None:
        return _audit_logger
    try:
        lg = logging.getLogger(AUDIT_LOGGER_NAME)
        lg.setLevel(logging.INFO)
        lg.propagate = False   # keep audit lines out of the app log/console
        if not lg.handlers:
            log_dir = os.path.dirname(AUDIT_LOG_FILE)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            handler = RotatingFileHandler(
                AUDIT_LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            lg.addHandler(handler)
        _audit_logger = lg
        return lg
    except Exception:
        return None


def record(event: Dict[str, Any]) -> None:
    """Write one audit event as a JSON line. Fail-silent."""
    if not settings.AUDIT_ENABLED:
        return
    lg = _get_audit_logger()
    if lg is None:
        return
    try:
        event.setdefault("ts", datetime.now(timezone.utc).isoformat())
        lg.info(json.dumps(event, ensure_ascii=False, default=str))
    except Exception:
        pass


def audit_turn(
    *,
    session_id: str,
    client_id: str,
    rm_id: str,
    route: str,
    query: str,
    response: str = "",
    outcome: str = "completed",
    tools_used: Optional[List[str]] = None,
    entitlement: str = "allowed",
    guardrail_flags: Optional[List[str]] = None,
    latency_ms: Optional[int] = None,
) -> None:
    """Build and persist a PII-redacted audit record for one turn."""
    record(
        {
            "session_id": session_id,
            "rm_id": rm_id,
            "client_id": client_id,
            "route": route,
            "outcome": outcome,
            "entitlement": entitlement,
            "guardrail_flags": guardrail_flags or [],
            "tools_used": tools_used or [],
            "latency_ms": latency_ms,
            "query": redact_pii((query or "")[:AUDIT_QUERY_MAX_LEN]),
            "response_preview": redact_pii((response or "")[:AUDIT_RESPONSE_MAX_LEN]),
        }
    )
