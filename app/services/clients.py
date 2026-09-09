"""Client roster loader — single source of truth for the demo client list.

Reads ``data/portfolio/clients.json`` when present and falls back to the
built-in ``DEFAULT_CLIENTS``. Used by the API routes (UI dropdown) and by the
clarification gate (to ground name-based disambiguation).
"""
from __future__ import annotations

import json
import os
from pathlib import Path as FilePath
from typing import Any, Dict, List

from app.constants import CLIENTS_DATA_FILE, DEFAULT_CLIENTS
from app.utils.logger import logger

# Absolute path to clients.json, resolved from the project root.
_CLIENTS_FILE = str(FilePath(__file__).resolve().parent.parent.parent / CLIENTS_DATA_FILE)


def load_clients() -> List[Dict[str, Any]]:
    """Return the client roster from clients.json, or DEFAULT_CLIENTS on any failure."""
    try:
        path = os.path.abspath(_CLIENTS_FILE)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            clients = data if isinstance(data, list) else data.get("clients", [])
            if clients:
                return clients
    except Exception as e:
        logger.warning(f"load_clients: falling back to defaults ({e})")
    return list(DEFAULT_CLIENTS)


def format_client_roster(clients: List[Dict[str, Any]]) -> str:
    """Render the roster as a compact 'id — name (segment)' list for prompts."""
    if not clients:
        return "(none)"
    parts = []
    for c in clients:
        cid = c.get("id", "?")
        name = c.get("name", "?")
        segment = c.get("segment")
        parts.append(f"{cid} — {name}" + (f" ({segment})" if segment else ""))
    return "; ".join(parts)
