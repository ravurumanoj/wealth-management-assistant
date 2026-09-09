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

# ── Input validation ──────────────────────────────────────────────────────────
MAX_SESSION_ID_LENGTH: int = 100
MAX_MESSAGE_LENGTH: int = 5000
SESSION_ID_REGEX: str = r"^[a-zA-Z0-9_-]+$"
CONTROL_CHAR_REGEX: str = r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB per log file before rotation
LOG_BACKUP_COUNT: int = 5
DEFAULT_LOGGER_NAME: str = "WMA-App"

# ── Database connection pool ──────────────────────────────────────────────────
DB_POOL_SIZE: int = 10
DB_MAX_OVERFLOW: int = 20

# ── Long-term memory caps (per client, enforced in long_term_repo) ────────────
LTM_MAX_EPISODIC: int = 50
LTM_MAX_SEMANTIC: int = 30
LTM_MAX_PROCEDURAL: int = 20
LTM_MAX_PREFERENCES: int = 40
SEMANTIC_MERGE_THRESHOLD: float = 0.88
EPISODIC_ANSWER_MAX_LEN: int = 800      # characters stored per answer
SEMANTIC_SOURCE_QUERY_MAX_LEN: int = 300  # characters stored per source query

# ── History / context truncation ─────────────────────────────────────────────
HISTORY_CONTENT_PREVIEW_LEN: int = 300   # chars kept per turn in summarise prompt
HISTORY_BLOCK_MAX_CONTENT_LEN: int = 200  # chars kept per turn in router history block

# ── Agent route labels ────────────────────────────────────────────────────────
ROUTE_PORTFOLIO_ONLY: str = "portfolio_only"
ROUTE_CRM_ONLY: str = "crm_only"
ROUTE_BOTH: str = "both"
ROUTE_GENERAL: str = "general"
ROUTE_GREETING: str = "greeting"
ROUTE_OUT_OF_SCOPE: str = "out_of_scope"
VALID_ROUTES: frozenset = frozenset(
    {
        ROUTE_PORTFOLIO_ONLY,
        ROUTE_CRM_ONLY,
        ROUTE_BOTH,
        ROUTE_GENERAL,
        ROUTE_GREETING,
        ROUTE_OUT_OF_SCOPE,
    }
)

# Routes that require data retrieval via the sub-agents (as opposed to a direct
# reply, safe decline, or a general no-tool answer).
DATA_ROUTES: frozenset = frozenset(
    {ROUTE_PORTFOLIO_ONLY, ROUTE_CRM_ONLY, ROUTE_BOTH}
)

# ── Execution mode (for the "both" route) ─────────────────────────────────────
# parallel   → sub-agents fetch independent data concurrently.
# sequential → producer runs first; its result is injected into the consumer.
EXEC_MODE_PARALLEL: str = "parallel"
EXEC_MODE_SEQUENTIAL: str = "sequential"
VALID_EXEC_MODES: frozenset = frozenset({EXEC_MODE_PARALLEL, EXEC_MODE_SEQUENTIAL})

# ── Sub-agent identifiers (producer/consumer + re-fetch targeting) ────────────
AGENT_PORTFOLIO: str = "portfolio"
AGENT_CRM: str = "crm"
VALID_AGENTS: frozenset = frozenset({AGENT_PORTFOLIO, AGENT_CRM})

# Max characters of a producer's result injected into the consumer's task
# instruction during sequential execution (keeps the handoff prompt bounded).
SEQUENTIAL_HANDOFF_MAX_LEN: int = 1500

# ── Clarification gate decisions (pre-dispatch) ───────────────────────────────
# proceed → query is specific enough; run the pipeline.
# clarify → query is ambiguous / under-specified; ask the RM before retrieving.
CLARIFY_PROCEED: str = "proceed"
CLARIFY_ASK: str = "clarify"
VALID_CLARIFY_ACTIONS: frozenset = frozenset({CLARIFY_PROCEED, CLARIFY_ASK})

# Label reported to the UI when a turn ends by asking the RM to disambiguate.
AGENT_USED_CLARIFICATION: str = "clarification"

# ── UI step-node keys (must match AGENT_LABELS in static/app.js) ──────────────
STEP_ROUTER: str = "router"
STEP_PORTFOLIO: str = "portfolio_insights"
STEP_CRM: str = "relationship_intelligence"
STEP_SYNTHESIZER: str = "synthesizer"
STEP_GENERAL: str = "general"
STEP_CLARIFICATION: str = "needs_clarification"

# Maps a sub-agent identifier to its UI step-node key.
AGENT_STEP_NODE: dict = {
    AGENT_PORTFOLIO: STEP_PORTFOLIO,
    AGENT_CRM: STEP_CRM,
}

# ── Safe-decline message (out-of-scope queries — deterministic, auditable) ────
SAFE_DECLINE_MESSAGE: str = (
    "I'm the Relationship Manager assistant, so I can only help with client "
    "portfolio insights and client relationship/meeting information. I can't help "
    "with that request, but feel free to ask me about a client's portfolio, "
    "performance, holdings, meetings, or follow-up actions."
)

# ── Governance: entitlements, audit, guardrails (Phase 5) ─────────────────────
ENTITLEMENTS_DATA_FILE: str = "data/entitlements.json"
DEFAULT_RM_ID: str = "RM-DEMO"
AUDIT_LOG_FILE: str = "logs/audit.log"
AUDIT_LOGGER_NAME: str = "WMA-Audit"

# agent_used labels for governance short-circuits (reported to the UI/audit).
AGENT_USED_BLOCKED: str = "blocked"
AGENT_USED_DENIED: str = "entitlement_denied"

# Guardrail decision categories.
GUARDRAIL_OK: str = "ok"
GUARDRAIL_INJECTION: str = "prompt_injection"
GUARDRAIL_DISALLOWED_ACTION: str = "disallowed_action"

# Message shown when an input guardrail blocks a request.
INPUT_BLOCKED_MESSAGE: str = (
    "I can't help with that request. I can share client portfolio and "
    "relationship information, but I can't take actions such as executing trades, "
    "sending messages, or changing records, and I can't override my instructions."
)

# Message shown when the RM is not entitled to the requested client/portfolio.
ENTITLEMENT_DENIED_MESSAGE: str = (
    "You don't appear to be authorized to view this client's information, or no "
    "authorized client is selected. Please select a client you're entitled to "
    "before I retrieve any portfolio or relationship data."
)

# Standard compliance disclaimer appended to data answers (FR-COM-008/012).
COMPLIANCE_DISCLAIMER: str = (
    "_This response is informational only, based on the cited sources, and is not "
    "investment advice or a recommendation._"
)

# Max characters of query/response persisted in an audit record.
AUDIT_QUERY_MAX_LEN: int = 1000
AUDIT_RESPONSE_MAX_LEN: int = 2000

# ── Data file names ───────────────────────────────────────────────────────────
PORTFOLIO_DATA_FILE: str = "portfolio.json"
CRM_DATA_FILE: str = "crm.json"
CLIENTS_DATA_FILE: str = "data/portfolio/clients.json"

# ── Sentinel / default values ─────────────────────────────────────────────────
DEFAULT_CLIENT_ID: str = "unknown"
DEMO_CLIENT_ID_PREFIX: str = "DEMO-"
DEMO_CLIENT_SEGMENT: str = "Demo"
DEMO_CLIENT_RISK_PROFILE: str = "moderate"
DEMO_CLIENT_RM: str = "Demo RM"

# ── SSE streaming response headers ───────────────────────────────────────────
SSE_RESPONSE_HEADERS: dict = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",   # disables nginx proxy buffering
    "Connection": "keep-alive",
}

# ── Default client list (fallback when clients.json is absent) ────────────────
DEFAULT_CLIENTS: list = [
    {"id": "CUST-1001", "name": "Rajesh Kumar", "segment": "HNI"},
    {"id": "CUST-1002", "name": "Priya Mehta", "segment": "HNI"},
    {"id": "CUST-2002", "name": "Priya Sharma", "segment": "Affluent"},
    {"id": "CUST-3003", "name": "Ananya Reddy", "segment": "Ultra-HNI"},
    {"id": "CUST-4004", "name": "Arjun Mehta", "segment": "Mass Affluent"},
    {"id": "CUST-5005", "name": "Kavita Nambiar", "segment": "HNI"},
]

# ── FastAPI metadata paths ────────────────────────────────────────────────────
DOCS_URL: str = "/docs"
REDOC_URL: str = "/redoc"
OPENAPI_URL: str = "/openapi.json"

# ── Health check status strings ───────────────────────────────────────────────
HEALTH_STATUS_HEALTHY: str = "healthy"
HEALTH_STATUS_DEGRADED: str = "degraded"

# ── LLM provider identifiers ──────────────────────────────────────────────────
LLM_PROVIDER_UNIQUE: str = "unique_ai"
LLM_PROVIDER_GEMINI: str = "gemini"
LLM_PROVIDER_OPENAI: str = "openai"

# ── Gemini model catalogue (reference values — active model set via config) ───
GEMINI_MODEL_2_FLASH: str = "gemini-2.0-flash"
GEMINI_MODEL_2_PRO: str = "gemini-2.0-pro-exp"
GEMINI_MODEL_15_PRO: str = "gemini-1.5-pro"
GEMINI_MODEL_15_FLASH: str = "gemini-1.5-flash"

# ── OpenAI model catalogue ────────────────────────────────────────────────────
OPENAI_MODEL_GPT4O: str = "gpt-4o"
OPENAI_MODEL_GPT4O_MINI: str = "gpt-4o-mini"
OPENAI_MODEL_GPT4_TURBO: str = "gpt-4-turbo"
OPENAI_MODEL_GPT35_TURBO: str = "gpt-3.5-turbo"

# ── LLM retry defaults (overridable via config) ───────────────────────────────
DEFAULT_LLM_MAX_RETRIES: int = 3
DEFAULT_LLM_RETRY_BASE_DELAY: float = 1.0
DEFAULT_LLM_RETRY_BACKOFF_MULTIPLIER: float = 2.0
DEFAULT_LLM_RETRY_MAX_DELAY: float = 30.0

# ── Model → provider routing table ───────────────────────────────────────────
# Used by detect_provider() in llm_base.py. Set LLM_FALLBACK_MODELS in .env
# using the model name constants defined above (e.g. "gemini-1.5-pro,gpt-4o").
MODEL_TO_PROVIDER: dict = {
    GEMINI_MODEL_2_FLASH:  LLM_PROVIDER_GEMINI,
    GEMINI_MODEL_2_PRO:    LLM_PROVIDER_GEMINI,
    GEMINI_MODEL_15_PRO:   LLM_PROVIDER_GEMINI,
    GEMINI_MODEL_15_FLASH: LLM_PROVIDER_GEMINI,
    OPENAI_MODEL_GPT4O:       LLM_PROVIDER_OPENAI,
    OPENAI_MODEL_GPT4O_MINI:  LLM_PROVIDER_OPENAI,
    OPENAI_MODEL_GPT4_TURBO:  LLM_PROVIDER_OPENAI,
    OPENAI_MODEL_GPT35_TURBO: LLM_PROVIDER_OPENAI,
}
