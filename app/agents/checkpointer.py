"""LangGraph short-term checkpointer (P4.1).

Persists per-thread graph state so a conversation (thread_id = session_id) can be
resumed. Prefers a Postgres saver when the ``langgraph-checkpoint-postgres`` extra
and the database are available; otherwise falls back to an in-memory saver so the
app keeps working. Returns ``None`` only when checkpointing is disabled or no saver
can be built.
"""
from __future__ import annotations

from urllib.parse import quote_plus

from app.config import settings
from app.utils.logger import logger

# Hold the Postgres context manager so its connection is not garbage-collected
# for the lifetime of the process.
_pg_cm = None


def _postgres_conn_string() -> str:
    """Build a psycopg-v3 connection URL from the POSTGRES_* settings."""
    password = quote_plus(settings.POSTGRES_PASSWORD)
    return (
        f"postgresql://{settings.POSTGRES_USER}:{password}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DATABASE}"
    )


def _build_postgres_checkpointer():
    """Create and set up a PostgresSaver; raises if the extra/DB is unavailable."""
    global _pg_cm
    from langgraph.checkpoint.postgres import PostgresSaver

    cm = PostgresSaver.from_conn_string(_postgres_conn_string())
    saver = cm.__enter__()
    saver.setup()          # creates checkpoint tables if missing (idempotent)
    _pg_cm = cm            # keep the connection open for the process lifetime
    return saver


def _build_memory_checkpointer():
    """Create an in-memory saver (works without any external service)."""
    try:
        from langgraph.checkpoint.memory import InMemorySaver
        return InMemorySaver()
    except Exception:
        from langgraph.checkpoint.memory import MemorySaver  # older alias
        return MemorySaver()


def build_checkpointer():
    """Return a LangGraph checkpointer, or ``None`` when disabled/unavailable."""
    if not settings.GRAPH_CHECKPOINTER_ENABLED:
        logger.info("graph checkpointer: disabled by config")
        return None

    try:
        checkpointer = _build_postgres_checkpointer()
        logger.info("graph checkpointer: PostgresSaver active")
        return checkpointer
    except Exception as e:
        logger.warning(
            f"graph checkpointer: Postgres unavailable "
            f"({type(e).__name__}: {e}); falling back to in-memory saver"
        )

    try:
        checkpointer = _build_memory_checkpointer()
        logger.info("graph checkpointer: InMemorySaver active")
        return checkpointer
    except Exception as e:
        logger.warning(f"graph checkpointer: none available ({type(e).__name__}: {e})")
        return None
