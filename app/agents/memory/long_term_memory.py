"""Long-term memory service — episodic, semantic, and procedural memory per client.

Currently disabled (LTM_DISABLED): save_turn_facts and format_long_term_context
return immediately. Re-enable when embeddings are available.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.utils.logger import logger
from app.repositories import long_term_repo
from app.constants import CTX_EPISODIC_LIMIT, CTX_SEMANTIC_LIMIT, CTX_PROCEDURAL_LIMIT
from app.prompts.memory import MEMORY_EXTRACTION_PROMPT

# ── context limits (imported from constants) ──────────────────────────────────
_CTX_EPISODIC = CTX_EPISODIC_LIMIT

# ── type aliases ──────────────────────────────────────────────────────────────
EpisodicEntry = Dict[str, Any]
SemanticFact = Dict[str, Any]
ProceduralPattern = Dict[str, Any]
ClientMemory = Dict[str, List]


def _categorize_preference(key: str) -> str:
    """Map a preference key to a coarse category for grouping/UI."""
    k = (key or "").lower()
    if any(t in k for t in ("risk", "volatility", "tolerance")):
        return "risk"
    if any(t in k for t in ("channel", "contact", "communication", "language", "report", "frequency")):
        return "communication"
    if any(t in k for t in ("invest", "sector", "fund", "tax", "goal", "horizon", "asset")):
        return "investment"
    return "general"


# ══════════════════════════════════════════════════════════════════════════════
# LEGACY JSON FILE I/O — DISABLED (replaced by MySQL via long_term_repo)
# ══════════════════════════════════════════════════════════════════════════════
# The helpers below (_MEMORY_FILE, _FILE_LOCK, _now, _load_all, _save_all,
# _client_store) read/wrote data/memory/long_term_memory.json. They are no
# longer used — all storage now goes through app.repositories.long_term_repo,
# which persists episodic/semantic/procedural memory in MySQL. The original
# JSON code is kept in version control for reference.


# ══════════════════════════════════════════════════════════════════════════════
# Public read / write API
# ══════════════════════════════════════════════════════════════════════════════

def load_client_memory(client_id: str) -> ClientMemory:
    """Return the raw memory bucket for *client_id*.

    Returns ``{episodic:[], semantic:[], procedural:[]}`` when the client
    has no prior memory (first session).

    Args:
        client_id: Wealth-management client identifier (e.g. ``"C1001"``).
    """
    return long_term_repo.get_client_memory(client_id)


def save_episodic(
    client_id: str,
    session_id: str,
    query: str,
    answer: str,
    intent: str,
    confidence: float = 1.0,
) -> None:
    """Append one Q&A episode to *episodic* memory for *client_id*.

    **Episodic memory** records every interaction so the assistant can say
    "in a previous session we discussed X". Persistence, answer truncation,
    and per-client eviction are handled by ``long_term_repo``.

    Args:
        client_id:  Client identifier (``"unknown"`` for unidentified clients).
        session_id: Session/thread ID that generated this episode.
        query:      The original user question.
        answer:     The final answer delivered to the user.
        intent:     Resolved intent (``portfolio_insights`` / ``general`` / …).
        confidence: LLM-assigned confidence (default 1.0 for this app).
    """
    long_term_repo.add_episodic(
        client_id=client_id,
        session_id=session_id,
        query=query,
        answer=answer,
        intent=intent,
        confidence=confidence,
    )
    logger.debug(f"long_term_memory [episodic] saved  client={client_id}")


def save_semantic_fact(
    client_id: str,
    fact: str,
    source_query: str,
    confidence: float = 0.85,
) -> None:
    """Persist an extracted semantic fact about *client_id*.

    **Semantic memory** holds durable facts: risk appetite, investment goals,
    life events, and declared preferences. Case-insensitive duplicates are
    rejected at the database level (unique ``(client_id, fact_hash)``).

    Args:
        client_id:    Client identifier.
        fact:         One concise sentence describing a client fact.
        source_query: The query that triggered this extraction.
        confidence:   LLM-assigned extraction confidence (0–1).
    """
    long_term_repo.add_semantic_fact(
        client_id=client_id,
        fact=fact,
        source_query=source_query,
        confidence=confidence,
    )
    logger.debug(f"long_term_memory [semantic] saved  client={client_id}")


def save_procedural_pattern(client_id: str, pattern: str) -> None:
    """Record a behavioural/communication pattern for *client_id*.

    **Procedural memory** tracks *how* the client interacts, not *what* they
    know. Duplicate patterns (case-insensitive) increment a ``frequency``
    counter and update ``last_seen`` instead of creating a new row.

    Args:
        client_id: Client identifier.
        pattern:   One concise sentence describing the observed pattern.
    """
    long_term_repo.upsert_procedural(client_id=client_id, pattern=pattern)
    logger.debug(f"long_term_memory [procedural] saved  client={client_id}")


def save_preference(
    client_id: str,
    pref_key: str,
    pref_value: str,
    category: str = "general",
    confidence: float = 0.8,
    source: str = "inferred",
) -> None:
    """Persist a structured client preference (``key → value``).

    **Preferences** are the actionable slice of long-term memory: risk
    tolerance, preferred communication channel, reporting cadence, investment
    style, sector interests. Unlike free-text semantic facts, each preference
    is a stable key whose value is overwritten on change (one row per key).

    Args:
        client_id:  Client identifier.
        pref_key:   Stable preference name (e.g. ``"risk_tolerance"``).
        pref_value: The preference value (e.g. ``"moderate"``).
        category:   Grouping bucket (``risk`` / ``investment`` /
                    ``communication`` / ``general``).
        confidence: Confidence in the preference (0–1).
        source:     ``"explicit"`` (user stated) or ``"inferred"``.
    """
    long_term_repo.upsert_preference(
        client_id=client_id,
        pref_key=pref_key,
        pref_value=pref_value,
        category=category,
        confidence=confidence,
        source=source,
    )
    logger.debug(f"long_term_memory [preference] saved  client={client_id} key={pref_key}")


def get_preferences(client_id: str) -> List[Dict[str, Any]]:
    """Return all stored preferences for *client_id* (may be empty)."""
    return long_term_repo.get_preferences(client_id)


def search_episodic(
    client_id: str,
    query: str,
    limit: int = _CTX_EPISODIC,
) -> List[EpisodicEntry]:
    """Return the most-relevant episodic entries for *query*.

    Relevance is measured by keyword overlap between the current query and
    each stored episode query. Falls back to the *limit* most-recent
    entries when no keyword overlap is found.

    Args:
        client_id: Client identifier.
        query:     Current user query used for relevance scoring.
        limit:     Maximum number of episodes to return.
    """
    return long_term_repo.search_episodic(client_id, query, limit=limit)


# ══════════════════════════════════════════════════════════════════════════════
# Context formatter — injected as SystemMessage at the top of every LLM call
# ══════════════════════════════════════════════════════════════════════════════

def format_long_term_context(client_id: str, query: str) -> Optional[str]:
    """Build a concise context block from all memory types for *client_id*."""
    # LTM_DISABLED — embeddings not available on this machine.
    # Remove this return to re-enable long-term memory context injection.
    return None


# ══════════════════════════════════════════════════════════════════════════════
# LLM-based fact extraction — called by save_turn_facts
# ══════════════════════════════════════════════════════════════════════════════

class ExtractedPreference(BaseModel):
    """A single structured client preference (key → value)."""

    key: str = Field(description="snake_case preference name, e.g. risk_tolerance")
    value: str = Field(description="the preference value, e.g. moderate")
    category: str = Field(
        default="general",
        description="one of: risk, investment, communication, general",
    )


class MemoryExtraction(BaseModel):
    """Structured long-term memory extracted from a single Q&A turn.

    Every list is empty when the turn contains nothing worth remembering (e.g.
    greetings / small talk), so the model — not hardcoded intent rules — decides
    what is noteworthy.
    """

    semantic_facts: List[str] = Field(
        default_factory=list,
        description=(
            "Durable facts about the client: goals, financial situation, life "
            "events, holdings context, declared constraints. One sentence each."
        ),
    )
    procedural_patterns: List[str] = Field(
        default_factory=list,
        description=(
            "How the client communicates: preferred output format, recurring "
            "topics, level of detail, question style. One sentence each."
        ),
    )
    preferences: List[ExtractedPreference] = Field(
        default_factory=list,
        description="Stable, actionable key=value preferences.",
    )


_EXTRACTION_INSTRUCTIONS = MEMORY_EXTRACTION_PROMPT  # alias for backward compat within module


def _heuristic_extract(query: str, answer: str) -> MemoryExtraction:
    """Best-effort line-format extraction used only if structured output fails.

    Keeps memory working on models/SDK versions where ``with_structured_output``
    is unavailable, without reintroducing intent-based gating.
    """
    try:
        from app.services.llm import get_llm
        from langchain_core.messages import HumanMessage

        prompt = (
            _EXTRACTION_INSTRUCTIONS
            + "\n\nRespond as plain lines, each prefixed with one of "
            "FACT:, PATTERN:, PREF: (PREF uses key=value). Use no other text.\n\n"
            f"Q: {query[:400]}\nA: {answer[:600]}\n"
        )
        result = get_llm().invoke([HumanMessage(content=prompt)])
        content = result.content
        if isinstance(content, list):
            raw = "".join(
                (p.get("text", "") if isinstance(p, dict) else str(p)) for p in content
            )
        else:
            raw = str(content or "")

        facts: List[str] = []
        patterns: List[str] = []
        prefs: List[ExtractedPreference] = []
        for line in raw.splitlines():
            line = line.strip()
            low = line.lower()
            if low.startswith("fact:"):
                val = line.split(":", 1)[1].strip()
                if val and val.lower() not in {"null", "none", "n/a"}:
                    facts.append(val)
            elif low.startswith("pattern:"):
                val = line.split(":", 1)[1].strip()
                if val and val.lower() not in {"null", "none", "n/a"}:
                    patterns.append(val)
            elif low.startswith("pref:"):
                val = line.split(":", 1)[1].strip()
                if "=" in val:
                    k, _, v = val.partition("=")
                    if k.strip() and v.strip():
                        prefs.append(
                            ExtractedPreference(
                                key=k.strip(),
                                value=v.strip(),
                                category=_categorize_preference(k),
                            )
                        )
        return MemoryExtraction(
            semantic_facts=facts, procedural_patterns=patterns, preferences=prefs
        )
    except Exception as e:
        logger.warning(
            f"long_term_memory: heuristic extraction failed "
            f"({type(e).__name__}: {e}) (non-fatal)"
        )
        return MemoryExtraction()


def _extract_memory(query: str, answer: str) -> MemoryExtraction:
    """Extract structured long-term memory from one Q&A turn.

    Uses the LLM's native structured-output (function-calling) so the result is
    a typed :class:`MemoryExtraction` instead of brittle string parsing. Falls
    back to a line-format heuristic, then to an empty extraction, so a failure
    never interrupts the main workflow.
    """
    try:
        from app.services.llm import get_llm
        from langchain_core.messages import HumanMessage

        prompt = (
            _EXTRACTION_INSTRUCTIONS
            + f"\n\nQ: {query[:400]}\nA: {answer[:600]}\n"
        )
        structured = get_llm().with_structured_output(MemoryExtraction)
        result = structured.invoke([HumanMessage(content=prompt)])
        if isinstance(result, MemoryExtraction):
            logger.info(
                f"long_term_memory: extracted facts={len(result.semantic_facts)} "
                f"patterns={len(result.procedural_patterns)} "
                f"prefs={len(result.preferences)}"
            )
            return result
        if isinstance(result, dict):
            return MemoryExtraction(**result)
        return MemoryExtraction()
    except Exception as e:
        logger.warning(
            f"long_term_memory: structured extraction failed "
            f"({type(e).__name__}: {e}); trying heuristic"
        )
        return _heuristic_extract(query, answer)


# ══════════════════════════════════════════════════════════════════════════════
# Main entry point — called after every completed LLM response
# ══════════════════════════════════════════════════════════════════════════════

def save_turn_facts(
    client_id: str,
    session_id: str,
    query: str,
    answer: str,
    intent: str,
) -> None:
    """Save all long-term memory artifacts for one completed Q&A turn."""
    # LTM_DISABLED — embeddings not available on this machine.
    # Remove this return to re-enable episodic/semantic/procedural saving.
    return





# ══════════════════════════════════════════════════════════════════════════════
# PostgreSQL integration (production)
# ══════════════════════════════════════════════════════════════════════════════
#
# When a PostgreSQL database is available, replace the MySQL backend with
# LangGraph's built-in PostgresStore.  Steps:
#
#   1. Install extras:
#          pip install "langgraph-checkpoint-postgres" "psycopg[binary]"
#
#   2. Add to .env:
#          POSTGRES_URL=postgresql://user:pass@host:5432/dbname
#
#   3. Implement the public functions above on top of PostgresStore.
#
# Memory namespaces follow the LangGraph convention (tuple of strings):
#   Episodic   -> (client_id, "episodic")
#   Semantic   -> (client_id, "semantic")
#   Procedural -> (client_id, "procedural")
