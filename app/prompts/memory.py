"""Prompts for the long-term memory extraction pipeline."""

# ── Episodic memory: per-turn "episode note" (the write-session-summary step) ──
# Distils one completed Q&A turn into a compact, client-specific note that is
# stored in long-term episodic memory and recalled in future sessions.
EPISODE_SUMMARY_PROMPT = (
    "You compress one Relationship Manager Q&A turn into a single memory note "
    "for future recall about THIS client.\n"
    "Write 1-2 concise sentences capturing what the RM asked and the key facts in "
    "the answer (figures, dates, decisions, concerns). Keep only durable, client-"
    "specific information. Do not add advice or anything not in the answer. "
    "Return only the note text."
)


MEMORY_EXTRACTION_PROMPT = (
    "You are a memory extractor for a wealth-management AI assistant.\n"
    "From the single Q&A turn below, extract only durable, client-specific "
    "information worth remembering across future sessions.\n"
    "- semantic_facts: durable facts (goals, financial situation, life events, constraints).\n"
    "- procedural_patterns: how the client likes to communicate (format, detail, recurring topics).\n"
    "- preferences: stable key=value settings "
    "(e.g. risk_tolerance=moderate, preferred_channel=email, sector_interest=pharma).\n"
    "Return EMPTY lists when the turn is small talk, a greeting, or contains "
    "nothing durable. Never invent information that is not supported by the turn."
)
