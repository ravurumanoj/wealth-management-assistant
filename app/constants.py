"""Application-wide constants.

All magic numbers and fixed string values live here.
Import from this module instead of hard-coding values in agent/service files.
"""

# ── Conversation history limits ───────────────────────────────────────────────
# Maximum prior conversation turns (user + assistant pairs) sent verbatim to LLM.
MAX_HISTORY_TURNS: int = 6

# When history exceeds this many messages the oldest turns are compressed into
# a rolling summary; the 4 most-recent messages are always kept verbatim.
HISTORY_SUMMARY_THRESHOLD: int = 10

# ── Retry / iteration caps ────────────────────────────────────────────────────
# Maximum tool-call rounds before the agent stops looping and answers anyway.
# NOTE: MCP_MAX_TOOL_ITERATIONS in config.py controls the per-request cap
# driven by env var; MAX_TOOL_ITERATIONS is the compile-time fallback.
MAX_TOOL_ITERATIONS: int = 5

# Maximum synthesizer retries when retrieved data is insufficient.
MAX_RETRIES: int = 2

# ── Long-term memory context limits ──────────────────────────────────────────
# Maximum recent episodic entries injected per prompt.
CTX_EPISODIC_LIMIT: int = 3

# Maximum semantic facts injected per prompt.
CTX_SEMANTIC_LIMIT: int = 15

# Maximum procedural patterns injected per prompt.
CTX_PROCEDURAL_LIMIT: int = 10
