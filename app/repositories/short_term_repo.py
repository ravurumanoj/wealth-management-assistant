"""Repository for short-term memory (chat sessions, messages, summaries)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select

from app.db.models import ChatMessage, ChatSession
from app.db.session import session_scope
from app.utils.logger import logger


def _ensure_session(db, session_id: str, client_id: Optional[str] = None) -> ChatSession:
    """Return the ChatSession row for *session_id*, creating it if absent.

    When *client_id* is supplied it is stamped onto the session: set on create,
    and back-filled on an existing row that is still ``"unknown"`` (so the first
    identified turn claims the session for that client).
    """
    obj = db.get(ChatSession, session_id)
    if obj is None:
        obj = ChatSession(session_id=session_id, client_id=client_id or "unknown")
        db.add(obj)
        db.flush()  # assign defaults without ending the transaction
    elif client_id and client_id != "unknown" and (obj.client_id or "unknown") == "unknown":
        obj.client_id = client_id
    return obj


def save_message(
    session_id: str,
    role: str,
    content: str,
    client_id: Optional[str] = None,
) -> None:
    """Append a message to a session, creating the session on first use.

    Args:
        session_id: Unique session identifier.
        role:       ``"user"`` or ``"assistant"``.
        content:    Message text.
        client_id:  Owning client; stamped onto the session so every message
                    can be traced back to a client.
    """
    try:
        with session_scope() as db:
            session = _ensure_session(db, session_id, client_id)
            session.messages.append(ChatMessage(role=role, content=content))
            session.last_updated = datetime.now(timezone.utc)
        logger.debug(f"short_term_repo: saved {role} message to session {session_id}")
    except Exception as e:
        logger.error(f"short_term_repo.save_message error: {e}")


def get_history(session_id: str) -> List[Dict[str, Any]]:
    """Return a session's messages in chronological order.

    Each item is ``{"role": str, "content": str, "timestamp": iso-str}`` to
    match the shape the agent nodes expect from the old JSON backend.
    """
    try:
        with session_scope() as db:
            rows = db.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at, ChatMessage.id)
            ).scalars().all()
            return [
                {
                    "role": r.role,
                    "content": r.content,
                    "timestamp": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"short_term_repo.get_history error: {e}")
        return []


def list_sessions(client_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return metadata for sessions, most-recently-updated first.

    Args:
        client_id: When provided, only that client's sessions are returned.
    """
    try:
        with session_scope() as db:
            count_sq = (
                select(
                    ChatMessage.session_id.label("sid"),
                    func.count(ChatMessage.id).label("cnt"),
                )
                .group_by(ChatMessage.session_id)
                .subquery()
            )
            stmt = (
                select(
                    ChatSession.session_id,
                    ChatSession.client_id,
                    ChatSession.created_at,
                    ChatSession.last_updated,
                    func.coalesce(count_sq.c.cnt, 0),
                )
                .outerjoin(count_sq, count_sq.c.sid == ChatSession.session_id)
                .order_by(ChatSession.last_updated.desc())
            )
            if client_id:
                stmt = stmt.where(ChatSession.client_id == client_id)
            rows = db.execute(stmt).all()
            return [
                {
                    "session_id": sid,
                    "client_id": cid or "unknown",
                    "created_at": created.isoformat() if created else "",
                    "last_updated": updated.isoformat() if updated else "",
                    "history_count": int(cnt),
                }
                for sid, cid, created, updated, cnt in rows
            ]
    except Exception as e:
        logger.error(f"short_term_repo.list_sessions error: {e}")
        return []


def delete_session(session_id: str) -> bool:
    """Delete a session and its messages (cascade). Returns ``True`` if found."""
    try:
        with session_scope() as db:
            obj = db.get(ChatSession, session_id)
            if obj is None:
                logger.warning(f"short_term_repo: session {session_id} not found for deletion")
                return False
            db.delete(obj)
        logger.info(f"short_term_repo: deleted session {session_id}")
        return True
    except Exception as e:
        logger.error(f"short_term_repo.delete_session error: {e}")
        return False


def clear_old_sessions(days: int = 30) -> int:
    """Delete sessions whose ``last_updated`` is older than *days*.

    Returns the number of sessions removed.
    """
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        with session_scope() as db:
            old_ids = db.execute(
                select(ChatSession.session_id).where(ChatSession.last_updated < cutoff)
            ).scalars().all()
            if not old_ids:
                return 0
            db.execute(delete(ChatSession).where(ChatSession.session_id.in_(old_ids)))
            count = len(old_ids)
        logger.info(f"short_term_repo: cleared {count} old sessions (> {days} days)")
        return count
    except Exception as e:
        logger.error(f"short_term_repo.clear_old_sessions error: {e}")
        return 0


def get_summary(session_id: str) -> Optional[str]:
    """Return the rolling short-term summary for a session, or ``None``."""
    try:
        with session_scope() as db:
            obj = db.get(ChatSession, session_id)
            return obj.summary if obj else None
    except Exception as e:
        logger.error(f"short_term_repo.get_summary error: {e}")
        return None


def save_summary(session_id: str, summary: str) -> None:
    """Persist the rolling short-term summary for a session."""
    try:
        with session_scope() as db:
            session = _ensure_session(db, session_id)
            session.summary = summary
            session.last_updated = datetime.now(timezone.utc)
        logger.debug(f"short_term_repo: saved summary for session {session_id}")
    except Exception as e:
        logger.error(f"short_term_repo.save_summary error: {e}")
