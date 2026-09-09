"""Long-term episodic memory — Qdrant in-memory store (P4.2).

Episodic memory ONLY: a per-client record of past interactions so the assistant
can recall, in a later session, what was previously asked and answered about a
client. Storage is an in-memory Qdrant instance (non-persistent, resets on
restart) with local fastembed embeddings — no external server or API key.

Concepts
--------
- Scope is the CLIENT (partition/filter = client_id); each point is tagged with
  the originating session_id and a timestamp.
- One point per completed data-turn. The stored "note" is a short distillation
  of the answer (the write-session-summary step), embedded together with the
  query for semantic recall.

Everything is lazy and fail-safe: if qdrant-client / fastembed are missing or a
model cannot load, the store disables itself and all methods become no-ops, so
the rest of the app is unaffected.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings
from app.prompts.memory import EPISODE_SUMMARY_PROMPT
from app.utils.logger import logger


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EpisodicMemoryStore:
    """Qdrant-backed per-client episodic memory (in-memory, fastembed)."""

    def __init__(self) -> None:
        self._client = None
        self._models = None
        self._disabled = not settings.LTM_ENABLED
        self._initialized = False

    # ── lazy initialization ───────────────────────────────────────────────────

    def _ensure_client(self) -> bool:
        """Create the in-memory Qdrant client + embedding model once. Never raises."""
        if self._disabled:
            return False
        if self._initialized:
            return self._client is not None
        self._initialized = True
        try:
            from qdrant_client import QdrantClient, models

            client = QdrantClient(location=settings.QDRANT_LOCATION)
            client.set_model(settings.QDRANT_EMBEDDING_MODEL)  # local fastembed model
            self._client = client
            self._models = models
            logger.info(
                f"episodic memory: Qdrant ready "
                f"(location={settings.QDRANT_LOCATION}, model={settings.QDRANT_EMBEDDING_MODEL})"
            )
            return True
        except Exception as e:
            self._disabled = True
            logger.warning(
                f"episodic memory: disabled ({type(e).__name__}: {e}); "
                "install qdrant-client[fastembed] to enable"
            )
            return False

    # ── write ─────────────────────────────────────────────────────────────────

    def add_episode(
        self,
        client_id: str,
        session_id: str,
        query: str,
        answer: str,
        intent: str,
    ) -> None:
        """Store one completed Q&A turn as an episode for *client_id*.

        No-op when memory is disabled, the client is unknown, or inputs are empty.
        Blocking (embeds + summarizes) — call via a worker thread from async code.
        """
        if not client_id or client_id == "unknown" or not query.strip():
            return
        if not self._ensure_client():
            return
        try:
            summary = self._summarize(query, answer)
            document = f"Q: {query}\nNote: {summary}"
            payload = {
                "client_id": client_id,
                "session_id": session_id,
                "intent": intent,
                "query": query,
                "summary": summary,
                "created_at": _now_iso(),
            }
            self._client.add(
                collection_name=settings.QDRANT_EPISODIC_COLLECTION,
                documents=[document],
                metadata=[payload],
                ids=[str(uuid.uuid4())],
            )
            logger.debug(f"episodic memory: stored episode client={client_id}")
        except Exception as e:
            logger.warning(f"episodic memory: add_episode failed ({type(e).__name__}: {e})")

    # ── read ──────────────────────────────────────────────────────────────────

    def search(
        self, client_id: str, query: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return the most-relevant past episodes for *client_id* and *query*.

        Blocking (embeds the query) — call via a worker thread from async code.
        """
        if not client_id or client_id == "unknown" or not query.strip():
            return []
        if not self._ensure_client():
            return []
        k = limit or settings.EPISODIC_TOP_K
        try:
            client_filter = self._models.Filter(
                must=[
                    self._models.FieldCondition(
                        key="client_id",
                        match=self._models.MatchValue(value=client_id),
                    )
                ]
            )
            hits = self._client.query(
                collection_name=settings.QDRANT_EPISODIC_COLLECTION,
                query_text=query,
                query_filter=client_filter,
                limit=k,
            )
            results: List[Dict[str, Any]] = []
            for h in hits:
                if getattr(h, "score", 0.0) < settings.EPISODIC_MIN_SCORE:
                    continue
                meta = getattr(h, "metadata", None) or {}
                results.append(
                    {
                        "query": meta.get("query", ""),
                        "summary": meta.get("summary", ""),
                        "intent": meta.get("intent", ""),
                        "created_at": meta.get("created_at", ""),
                        "score": round(float(getattr(h, "score", 0.0)), 3),
                    }
                )
            return results
        except Exception as e:
            logger.warning(f"episodic memory: search failed ({type(e).__name__}: {e})")
            return []

    @staticmethod
    def format_context(episodes: List[Dict[str, Any]]) -> str:
        """Render episodes as a compact context block, or '' when there are none."""
        if not episodes:
            return ""
        lines = ["Relevant prior interactions with this client (long-term memory):"]
        for ep in episodes:
            date = (ep.get("created_at", "") or "")[:10]
            note = ep.get("summary") or ep.get("query") or ""
            lines.append(f"- [{date}] {note}".rstrip())
        return "\n".join(lines)

    # ── internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _summarize(query: str, answer: str) -> str:
        """Distil the turn into a short note; fall back to a truncated answer."""
        max_len = settings.EPISODIC_SUMMARY_MAX_LEN
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            from app.agents.base import extract_text, get_shared_llm

            msgs = [
                SystemMessage(content=EPISODE_SUMMARY_PROMPT),
                HumanMessage(content=f"Q: {query[:600]}\nA: {answer[:1500]}"),
            ]
            note = extract_text(get_shared_llm().invoke(msgs).content).strip()
            if note:
                return note[:max_len]
        except Exception as e:
            logger.warning(f"episodic memory: summary fell back ({type(e).__name__}: {e})")
        return (answer or query).strip()[:max_len]


# Module-level singleton shared across the orchestrator and graph.
episodic_memory = EpisodicMemoryStore()
