"""Prompts for the long-term memory extraction pipeline."""

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
