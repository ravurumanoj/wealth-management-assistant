"""MCP client for the CRM agent.

Connects to the configured MCP server, discovers tools at runtime, and returns
them as LangChain tools. Returns an empty list on any failure so the app
continues working without MCP configured. Results are cached per process.
"""
from __future__ import annotations

import asyncio
from typing import List

from app.config import settings
from app.utils.logger import logger

# Cache of the discovered LangChain tools (populated on first successful load).
_mcp_tools_cache: List | None = None
# Ensures the "MCP is not configured / disabled" message is logged only once.
_disabled_logged = False


def is_mcp_configured() -> bool:
    """Return True only when MCP is enabled *and* a server URL has been set."""
    return bool(settings.MCP_ENABLED and settings.MCP_CRM_SERVER_URL)


def reset_mcp_cache() -> None:
    """Clear the cached tool list so the next call re-discovers from the server."""
    global _mcp_tools_cache
    _mcp_tools_cache = None


async def get_mcp_tools() -> List:
    """Discover and return the CRM MCP server's tools as LangChain tools.

    Never raises — returns an empty list on any failure so the caller can fall
    back to built-in tools.
    """
    global _mcp_tools_cache, _disabled_logged

    # ── Scenarios 1 & 2: MCP off or URL not configured ────────────────────────
    if not is_mcp_configured():
        if not _disabled_logged:
            reason = (
                "MCP_ENABLED is False"
                if not settings.MCP_ENABLED
                else "MCP_CRM_SERVER_URL is not set"
            )
            logger.info(
                f"MCP CRM tools unavailable ({reason}); "
                "Relationship agent will use its built-in CRM tool."
            )
            _disabled_logged = True
        return []

    # ── Cached result from a previous successful discovery ────────────────────
    if _mcp_tools_cache is not None:
        return _mcp_tools_cache

    # ── Scenario 3: adapter package not installed ─────────────────────────────
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning(
            "langchain-mcp-adapters is not installed; MCP disabled. "
            "Run `uv add langchain-mcp-adapters mcp` (or `pip install` them) to enable it."
        )
        return []

    # ── Scenarios 4 & 5: connect + discover with a timeout ────────────────────
    try:
        client = MultiServerMCPClient(
            {
                "crm": {
                    "url": settings.MCP_CRM_SERVER_URL,
                    "transport": settings.MCP_TRANSPORT,  # "streamable_http"
                }
            }
        )
        tools = await asyncio.wait_for(
            client.get_tools(), timeout=settings.MCP_TIMEOUT
        )
        if not tools:
            logger.warning(
                "MCP CRM server returned no tools; falling back to built-in CRM tool."
            )
            return []

        _mcp_tools_cache = tools
        tool_names = ", ".join(getattr(t, "name", "?") for t in tools)
        logger.info(
            f"Discovered {len(tools)} MCP CRM tool(s) from "
            f"{settings.MCP_CRM_SERVER_URL}: {tool_names}"
        )
        return tools
    except asyncio.TimeoutError:
        logger.warning(
            f"MCP CRM server timed out after {settings.MCP_TIMEOUT}s "
            f"({settings.MCP_CRM_SERVER_URL}); falling back to built-in CRM tool."
        )
        return []
    except Exception as e:  # noqa: BLE001 — must never propagate to the agent
        logger.warning(
            f"MCP CRM tool discovery failed ({e}); falling back to built-in CRM tool."
        )
        return []
