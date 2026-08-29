import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

# Absolute path to .env so the file is found regardless of working directory
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

class Settings(BaseSettings):
    """Application settings — loaded from environment variables or .env file."""
    # Application Info
    APP_NAME: str = "Wealth Management Assistant"
    API_V1_STR: str = "/api/v1"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Agentic RAG-powered Wealth Management Assistant using LangGraph"
    
    # Server Settings
    HOST: str = "0.0.0.0"  # Listen on all interfaces - access via localhost or IP
    PORT: int = 8000
    DEBUG: bool = True
    RELOAD: bool = True  # Auto-reload on code changes

    # ── Google Gemini LLM Settings (DISABLED — Unique AI is active) ─────────
    # GEMINI_DISABLED: commented out but kept for reference / easy re-enable
    # GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    # GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    # GEMINI_TEMPERATURE: float = float(os.getenv("GEMINI_TEMPERATURE", 0.7))
    # GEMINI_MAX_TOKENS: int = int(os.getenv("GEMINI_MAX_TOKENS", 8192))
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")  # kept for health-check only

    # ── Unique AI LLM Settings (active) ──────────────────────────────────────
    UNIQUE_API_BASE_URL: str = ""
    UNIQUE_MODEL_NAME: str = ""
    UNIQUE_APP_ID: str = ""
    UNIQUE_APP_KEY: str = ""
    UNIQUE_COMPANY_ID: str = ""
    UNIQUE_USER_ID: str = ""
    # Path to corporate CA certificate bundle (.pem/.crt) — set when SSL errors occur
    SSL_CA_CERT_PATH: str = ""
    # Set to False to disable SSL verification (use only for local testing, not production)
    SSL_VERIFY: bool = True

    EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    MEMORY_STORAGE_PATH: str = "data/memory/sessions.json"
    LONG_TERM_MEMORY_PATH: str = "data/memory/long_term_memory.json"

    # ── MySQL Memory Database Settings (DISABLED — PostgreSQL is active) ─────────
    # MYSQL_HOST: str = "localhost"
    # MYSQL_PORT: int = 3306
    # MYSQL_USER: str = "root"
    # MYSQL_PASSWORD: str = ""
    # MYSQL_DATABASE: str = "wealth_memory"

    # ── PostgreSQL Memory Database Settings (active) ─────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DATABASE: str = "wealth_memory"
    MEMORY_DATABASE_URL_OVERRIDE: Optional[str] = None
    DB_ECHO: bool = False

    @property
    def MEMORY_DATABASE_URL(self) -> str:
        """Return the SQLAlchemy connection URL for the memory database."""
        if self.MEMORY_DATABASE_URL_OVERRIDE:
            return self.MEMORY_DATABASE_URL_OVERRIDE
        from urllib.parse import quote_plus
        password = quote_plus(self.POSTGRES_PASSWORD)
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"
        )

    # ── MCP Settings ─────────────────────────────────────────────────────────
    MCP_ENABLED: bool = True
    MCP_CRM_SERVER_URL: Optional[str] = None
    MCP_TRANSPORT: str = "streamable_http"
    MCP_TIMEOUT: float = 15.0
    MCP_MAX_TOOL_ITERATIONS: int = 5

    # ── LLM Provider Selection ────────────────────────────────────────────────
    # Active primary provider: "unique_ai" | "gemini" | "openai"
    LLM_PROVIDER: str = "unique_ai"
    # Ordered fallback MODEL names (not providers). Example: "gemini-1.5-pro,gpt-4o"
    # Provider is auto-detected from the model name via MODEL_TO_PROVIDER registry.
    LLM_FALLBACK_MODELS: str = ""

    # ── Retry / backoff ───────────────────────────────────────────────────────
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BASE_DELAY: float = 1.0        # seconds before first retry
    LLM_RETRY_BACKOFF_MULTIPLIER: float = 2.0 # multiplier per retry attempt
    LLM_RETRY_MAX_DELAY: float = 30.0         # hard cap on inter-retry wait

    # ── Gemini Settings ───────────────────────────────────────────────────────
    GEMINI_MODEL: str = "gemini-1.5-pro"
    GEMINI_TEMPERATURE: float = 0.7
    GEMINI_MAX_TOKENS: int = 8192

    # ── OpenAI Settings ───────────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.7
    OPENAI_MAX_TOKENS: int = 8192
    # Optional: Azure OpenAI endpoint or any OpenAI-compatible base URL
    OPENAI_BASE_URL: str = ""

    # ── Proxy Settings ────────────────────────────────────────────────────────
    # Corporate / client-side proxy. Leave empty in production environments.
    HTTP_PROXY: str = ""
    HTTPS_PROXY: str = ""

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    ENABLE_FILE_LOGGING: bool = True
    LOG_FILE: str = "logs/app.log"

    BACKEND_CORS_ORIGINS: list = ["*"]
    DEFAULT_AGENT_TIMEOUT: int = 60
    MAX_AGENT_ITERATIONS: int = 5

    @property
    def LLM_FALLBACK_MODELS_LIST(self) -> list[str]:
        """Return the fallback model list parsed from the comma-separated string."""
        if not self.LLM_FALLBACK_MODELS:
            return []
        return [m.strip() for m in self.LLM_FALLBACK_MODELS.split(",") if m.strip()]

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

settings = Settings()


