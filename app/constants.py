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
VALID_ROUTES: frozenset = frozenset(
    {ROUTE_PORTFOLIO_ONLY, ROUTE_CRM_ONLY, ROUTE_BOTH, ROUTE_GENERAL}
)

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
