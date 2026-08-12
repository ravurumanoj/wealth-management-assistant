"""Repository for long-term memory (episodic, semantic, procedural) — PostgreSQL-backed."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from sqlalchemy import delete, select

from app.db.models import (
    ClientPreference,
    EpisodicMemory,
    ProceduralMemory,
    SemanticMemory,
)
from app.db.session import session_scope
# LTM_DISABLED — embeddings disabled; uncomment when available
# from app.services import embeddings
from app.utils.logger import logger

# ── per-client caps (mirror the previous JSON backend) ──────────────────────────
_MAX_EPISODIC: int = 50    # keep last 50 Q&A episodes
_MAX_SEMANTIC: int = 30    # keep last 30 extracted facts
_MAX_PROCEDURAL: int = 20  # keep last 20 behavioural patterns
_MAX_PREFERENCES: int = 40  # keep up to 40 preference keys per client

# Cosine-similarity threshold above which a "new" semantic fact is treated as a
# restatement of an existing one and updated in place rather than appended.
_SEMANTIC_MERGE_THRESHOLD: float = 0.88


def _now() -> datetime:
    """Current UTC time as a timezone-aware ``datetime``."""
    return datetime.now(timezone.utc)


def _hash(text: str) -> str:
    """Return the SHA-256 hex digest of the normalised *text* (for dedup)."""
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# Episodic
# ══════════════════════════════════════════════════════════════════════════════

def add_episodic(
    client_id: str,
    session_id: str,
    query: str,
    answer: str,
    intent: str,
    confidence: float = 1.0,
) -> None:
    """Insert one Q&A episode and evict episodes beyond the per-client cap."""
    try:
        # LTM_DISABLED — embedding generation skipped
        # embedding_blob = embeddings.encode_embedding(embeddings.embed_text(query))
        embedding_blob = None
        with session_scope() as db:
            db.add(
                EpisodicMemory(
                    id=str(uuid.uuid4()),
                    client_id=client_id,
                    session_id=session_id,
                    query=query,
                    answer=answer[:800],
                    intent=intent,
                    confidence=round(confidence, 3),
                    embedding=embedding_blob,
                    created_at=_now(),
                )
            )
            db.flush()
            _trim_episodic(db, client_id)
        logger.debug(f"long_term_repo: episodic saved client={client_id}")
    except Exception as e:
        logger.warning(f"long_term_repo.add_episodic error: {e}")


def _trim_episodic(db, client_id: str) -> None:
    """Keep only the most-recent ``_MAX_EPISODIC`` episodes for a client."""
    ids = db.execute(
        select(EpisodicMemory.id)
        .where(EpisodicMemory.client_id == client_id)
        .order_by(EpisodicMemory.created_at.desc(), EpisodicMemory.id.desc())
        .offset(_MAX_EPISODIC)
    ).scalars().all()
    if ids:
        db.execute(delete(EpisodicMemory).where(EpisodicMemory.id.in_(ids)))


def search_episodic(client_id: str, query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Return the most-relevant episodes for *query*.

    Retrieval strategy (best-effort, always safe):

    1. **Semantic** — embed the query, build a temporary numpy index from the
       embeddings stored on the client's recent episodes, and cosine-rank.
    2. **Keyword fallback** — when embeddings are unavailable (no API key /
       legacy rows / empty query), fall back to keyword overlap, then to
       most-recent. This preserves the original behaviour.
    """
    try:
        with session_scope() as db:
            rows = db.execute(
                select(EpisodicMemory)
                .where(EpisodicMemory.client_id == client_id)
                .order_by(EpisodicMemory.created_at.desc(), EpisodicMemory.id.desc())
                .limit(_MAX_EPISODIC)
            ).scalars().all()
        if not rows:
            return []
        episodes = [
            {
                "id": r.id,
                "timestamp": r.created_at.isoformat() if r.created_at else "",
                "session_id": r.session_id,
                "query": r.query,
                "answer": r.answer,
                "intent": r.intent,
                "confidence": float(r.confidence) if r.confidence is not None else 1.0,
                "_embedding": r.embedding,
            }
            for r in rows
        ]

        # LTM_DISABLED — semantic ranking via embedding skipped; keyword fallback always used
        # query_vec = embeddings.embed_text(query) if query else None
        # if query_vec is not None:
        #     candidates = [embeddings.decode_embedding(e["_embedding"]) for e in episodes]
        #     scores = embeddings.cosine_rank(query_vec, candidates)
        #     if any(s > 0 for s in scores):
        #         ranked = sorted(zip(scores, episodes), key=lambda t: t[0], reverse=True)
        #         return [_strip_internal(ep) for score, ep in ranked[:limit] if score > 0]
        query_vec = None  # LTM_DISABLED

        # ── 2. Keyword overlap fallback ──────────────────────────────────────
        query_words = set(query.lower().split())

        def _score(ep: Dict[str, Any]) -> int:
            return len(query_words & set(ep.get("query", "").lower().split()))

        scored = sorted(episodes, key=_score, reverse=True)
        if not scored or _score(scored[0]) == 0:
            scored = episodes  # already most-recent first
        return [_strip_internal(ep) for ep in scored[:limit]]
    except Exception as e:
        logger.warning(f"long_term_repo.search_episodic error: {e}")
        return []


def _strip_internal(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Drop transient ``_``-prefixed helper keys before returning to callers."""
    return {k: v for k, v in entry.items() if not k.startswith("_")}


# ══════════════════════════════════════════════════════════════════════════════
# Semantic
# ══════════════════════════════════════════════════════════════════════════════

def add_semantic_fact(
    client_id: str,
    fact: str,
    source_query: str,
    confidence: float = 0.85,
) -> None:
    """Insert a semantic fact, or **update** a semantically equivalent one.

    Reconciliation order:

    1. **Exact dedup** — identical (normalised) fact already stored → no-op.
    2. **Semantic merge** — if an existing fact is highly similar (cosine ≥
       ``_SEMANTIC_MERGE_THRESHOLD``), the stored fact is *overwritten* with the
       latest wording, embedding, confidence and timestamp. This is how the
       client model stays current ("risk appetite is low" → later "risk
       appetite is moderate" updates the same row instead of contradicting it).
    3. **Insert** — otherwise a new fact row is added.

    The unique ``(client_id, fact_hash)`` constraint still guards against exact
    duplicates inserted concurrently.
    """
    fact = fact.strip()
    if not fact:
        return
    fact_hash = _hash(fact)
    # LTM_DISABLED — embedding generation and semantic merge skipped
    # new_vec = embeddings.embed_text(fact)
    # embedding_blob = embeddings.encode_embedding(new_vec)
    new_vec = None
    embedding_blob = None
    try:
        with session_scope() as db:
            # 1. exact duplicate
            exists = db.execute(
                select(SemanticMemory.id).where(
                    SemanticMemory.client_id == client_id,
                    SemanticMemory.fact_hash == fact_hash,
                )
            ).first()
            if exists:
                return  # deduplicate

            # 2. semantic near-duplicate → update in place
            # LTM_DISABLED — cosine dedup skipped; exact hash dedup above still active
            # if new_vec is not None:
            #     rows = db.execute(...).scalars().all()
            #     candidates = [embeddings.decode_embedding(r.embedding) for r in rows]
            #     scores = embeddings.cosine_rank(new_vec, candidates)
            #     if scores[best_i] >= _SEMANTIC_MERGE_THRESHOLD: ... return

            # 3. insert new
            db.add(
                SemanticMemory(
                    id=str(uuid.uuid4()),
                    client_id=client_id,
                    fact=fact,
                    fact_hash=fact_hash,
                    confidence=round(confidence, 3),
                    source_query=source_query[:300],
                    embedding=embedding_blob,
                    created_at=_now(),
                )
            )
            db.flush()
            _trim_semantic(db, client_id)
        logger.debug(f"long_term_repo: semantic saved client={client_id}")
    except Exception as e:
        logger.warning(f"long_term_repo.add_semantic_fact error: {e}")


def _trim_semantic(db, client_id: str) -> None:
    """Keep only the most-recent ``_MAX_SEMANTIC`` facts for a client."""
    ids = db.execute(
        select(SemanticMemory.id)
        .where(SemanticMemory.client_id == client_id)
        .order_by(SemanticMemory.created_at.desc(), SemanticMemory.id.desc())
        .offset(_MAX_SEMANTIC)
    ).scalars().all()
    if ids:
        db.execute(delete(SemanticMemory).where(SemanticMemory.id.in_(ids)))


def recent_semantic(client_id: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Return the *limit* most-recent semantic facts (oldest→newest)."""
    try:
        with session_scope() as db:
            rows = db.execute(
                select(SemanticMemory)
                .where(SemanticMemory.client_id == client_id)
                .order_by(SemanticMemory.created_at.desc(), SemanticMemory.id.desc())
                .limit(limit)
            ).scalars().all()
        rows = list(reversed(rows))  # present oldest→newest like the JSON tail slice
        return [
            {
                "id": r.id,
                "timestamp": r.created_at.isoformat() if r.created_at else "",
                "fact": r.fact,
                "confidence": float(r.confidence) if r.confidence is not None else 0.85,
                "source_query": r.source_query,
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"long_term_repo.recent_semantic error: {e}")
        return []


def search_semantic(client_id: str, query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """Return the most-relevant semantic facts for *query*."""
    # LTM_DISABLED — vector search skipped; falls back to most-recent facts
    # Uncomment the full implementation below when embeddings are available
    # query_vec = embeddings.embed_text(query) if query else None
    # ...
    return recent_semantic(client_id, limit=limit)


# ══════════════════════════════════════════════════════════════════════════════
# Procedural
# ══════════════════════════════════════════════════════════════════════════════

def upsert_procedural(client_id: str, pattern: str) -> None:
    """Insert a behavioural pattern, or bump its frequency if already seen."""
    pattern = pattern.strip()
    if not pattern:
        return
    pattern_hash = _hash(pattern)
    try:
        with session_scope() as db:
            existing = db.execute(
                select(ProceduralMemory).where(
                    ProceduralMemory.client_id == client_id,
                    ProceduralMemory.pattern_hash == pattern_hash,
                )
            ).scalars().first()
            if existing:
                existing.frequency = (existing.frequency or 1) + 1
                existing.last_seen = _now()
                logger.debug(f"long_term_repo: procedural freq++ client={client_id}")
                return
            db.add(
                ProceduralMemory(
                    id=str(uuid.uuid4()),
                    client_id=client_id,
                    pattern=pattern,
                    pattern_hash=pattern_hash,
                    frequency=1,
                    created_at=_now(),
                    last_seen=_now(),
                )
            )
            db.flush()
            _trim_procedural(db, client_id)
        logger.debug(f"long_term_repo: procedural saved client={client_id}")
    except Exception as e:
        logger.warning(f"long_term_repo.upsert_procedural error: {e}")


def _trim_procedural(db, client_id: str) -> None:
    """Keep only the top ``_MAX_PROCEDURAL`` patterns (by frequency) per client."""
    ids = db.execute(
        select(ProceduralMemory.id)
        .where(ProceduralMemory.client_id == client_id)
        .order_by(ProceduralMemory.frequency.desc(), ProceduralMemory.last_seen.desc())
        .offset(_MAX_PROCEDURAL)
    ).scalars().all()
    if ids:
        db.execute(delete(ProceduralMemory).where(ProceduralMemory.id.in_(ids)))


def top_procedural(client_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return the top *limit* patterns for a client, highest-frequency first."""
    try:
        with session_scope() as db:
            rows = db.execute(
                select(ProceduralMemory)
                .where(ProceduralMemory.client_id == client_id)
                .order_by(ProceduralMemory.frequency.desc(), ProceduralMemory.last_seen.desc())
                .limit(limit)
            ).scalars().all()
        return [
            {
                "id": r.id,
                "timestamp": r.created_at.isoformat() if r.created_at else "",
                "last_seen": r.last_seen.isoformat() if r.last_seen else "",
                "pattern": r.pattern,
                "frequency": int(r.frequency or 1),
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"long_term_repo.top_procedural error: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Preferences
# ══════════════════════════════════════════════════════════════════════════════

def upsert_preference(
    client_id: str,
    pref_key: str,
    pref_value: str,
    category: str = "general",
    confidence: float = 0.8,
    source: str = "inferred",
) -> None:
    """Insert a preference, or overwrite the value if the key already exists.

    Uniqueness is enforced on ``(client_id, pref_key)`` so each client holds a
    single value per preference key; a newer value replaces the old one and
    bumps ``updated_at``.
    """
    pref_key = (pref_key or "").strip().lower().replace(" ", "_")
    pref_value = (pref_value or "").strip()
    if not pref_key or not pref_value:
        return
    try:
        with session_scope() as db:
            existing = db.execute(
                select(ClientPreference).where(
                    ClientPreference.client_id == client_id,
                    ClientPreference.pref_key == pref_key,
                )
            ).scalars().first()
            if existing:
                existing.pref_value = pref_value
                existing.category = category or existing.category
                existing.confidence = round(confidence, 3)
                existing.source = source or existing.source
                existing.updated_at = _now()
                logger.debug(f"long_term_repo: preference updated client={client_id} key={pref_key}")
                return
            db.add(
                ClientPreference(
                    id=str(uuid.uuid4()),
                    client_id=client_id,
                    category=category or "general",
                    pref_key=pref_key,
                    pref_value=pref_value,
                    confidence=round(confidence, 3),
                    source=source or "inferred",
                    created_at=_now(),
                    updated_at=_now(),
                )
            )
            db.flush()
            _trim_preferences(db, client_id)
        logger.debug(f"long_term_repo: preference saved client={client_id} key={pref_key}")
    except Exception as e:
        logger.warning(f"long_term_repo.upsert_preference error: {e}")


def _trim_preferences(db, client_id: str) -> None:
    """Keep only the most-recent ``_MAX_PREFERENCES`` keys for a client."""
    ids = db.execute(
        select(ClientPreference.id)
        .where(ClientPreference.client_id == client_id)
        .order_by(ClientPreference.updated_at.desc(), ClientPreference.id.desc())
        .offset(_MAX_PREFERENCES)
    ).scalars().all()
    if ids:
        db.execute(delete(ClientPreference).where(ClientPreference.id.in_(ids)))


def get_preferences(client_id: str, limit: int = _MAX_PREFERENCES) -> List[Dict[str, Any]]:
    """Return a client's preferences, grouped-friendly and most-recent first."""
    try:
        with session_scope() as db:
            rows = db.execute(
                select(ClientPreference)
                .where(ClientPreference.client_id == client_id)
                .order_by(ClientPreference.category, ClientPreference.pref_key)
                .limit(limit)
            ).scalars().all()
        return [
            {
                "id": r.id,
                "category": r.category,
                "key": r.pref_key,
                "value": r.pref_value,
                "confidence": float(r.confidence) if r.confidence is not None else 0.8,
                "source": r.source,
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning(f"long_term_repo.get_preferences error: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════════════
# Aggregate read
# ══════════════════════════════════════════════════════════════════════════════

def get_client_memory(client_id: str) -> Dict[str, List[Dict[str, Any]]]:
    """Return the full memory bucket for a client.

    Shape mirrors the old JSON store, with preferences added::

        {"episodic": [...], "semantic": [...], "procedural": [...],
         "preferences": [...]}
    """
    return {
        "episodic": search_episodic(client_id, query="", limit=_MAX_EPISODIC),
        "semantic": recent_semantic(client_id, limit=_MAX_SEMANTIC),
        "procedural": top_procedural(client_id, limit=_MAX_PROCEDURAL),
        "preferences": get_preferences(client_id, limit=_MAX_PREFERENCES),
    }
