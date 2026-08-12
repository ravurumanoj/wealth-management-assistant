"""Embedding helpers for semantic memory retrieval (currently disabled — LTM_DISABLED)."""
from __future__ import annotations

import json
from typing import List, Optional

import numpy as np

from app.config import settings
from app.utils.logger import logger

# Google embedding model — configurable via settings.EMBEDDING_MODEL. Must
# support `embedContent` for the configured API key. Same key as the chat model.
_EMBED_MODEL = settings.EMBEDDING_MODEL

_embeddings_client = None
_embeddings_disabled = False


def _get_client():
    """Return a lazily-created singleton embeddings client, or ``None``.

    Disables itself permanently after the first hard failure so we don't retry
    a broken configuration on every turn.
    """
    global _embeddings_client, _embeddings_disabled
    if _embeddings_disabled:
        return None
    if _embeddings_client is not None:
        return _embeddings_client
    if not settings.GOOGLE_API_KEY:
        logger.warning("embeddings: GOOGLE_API_KEY not set — semantic search disabled")
        _embeddings_disabled = True
        return None
    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        _embeddings_client = GoogleGenerativeAIEmbeddings(
            model=_EMBED_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
        )
        logger.info(f"embeddings: initialised {_EMBED_MODEL}")
        return _embeddings_client
    except Exception as e:
        logger.warning(f"embeddings: init failed ({type(e).__name__}: {e}) — disabling")
        _embeddings_disabled = True
        return None


def embed_text(text: str) -> Optional[List[float]]:
    """Embed a single string. Returns ``None`` on any failure or empty input."""
    text = (text or "").strip()
    if not text:
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        return client.embed_query(text)
    except Exception as e:
        logger.warning(f"embeddings.embed_text failed ({type(e).__name__}: {e})")
        return None


def encode_embedding(vector: Optional[List[float]]) -> Optional[str]:
    """Serialise an embedding vector to a compact JSON string for DB storage."""
    if not vector:
        return None
    try:
        return json.dumps([round(float(x), 6) for x in vector])
    except Exception:
        return None


def decode_embedding(blob: Optional[str]) -> Optional[np.ndarray]:
    """Deserialise a stored JSON embedding back into a numpy vector."""
    if not blob:
        return None
    try:
        arr = np.asarray(json.loads(blob), dtype=np.float32)
        return arr if arr.size else None
    except Exception:
        return None


def cosine_rank(
    query_vec: List[float],
    candidates: List[Optional[np.ndarray]],
) -> List[float]:
    """Return cosine-similarity scores of *query_vec* against each candidate.

    Builds a temporary numpy matrix (the ephemeral "index") from the candidate
    vectors and computes cosine similarity in one vectorised pass. Candidates
    that are ``None`` (no stored embedding) score ``-1.0`` so they sort last.

    Args:
        query_vec:  The query embedding.
        candidates: Per-row embedding vectors (some may be ``None``).

    Returns:
        A list of float scores aligned with *candidates*.
    """
    q = np.asarray(query_vec, dtype=np.float32)
    q_norm = float(np.linalg.norm(q))
    if q_norm == 0.0:
        return [-1.0] * len(candidates)
    q = q / q_norm

    scores: List[float] = []
    for vec in candidates:
        if vec is None or vec.size != q.size:
            scores.append(-1.0)
            continue
        v_norm = float(np.linalg.norm(vec))
        if v_norm == 0.0:
            scores.append(-1.0)
            continue
        scores.append(float(np.dot(q, vec / v_norm)))
    return scores
