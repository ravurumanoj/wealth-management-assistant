import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

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
    UNIQUE_API_BASE_URL: str = os.getenv("UNIQUE_API_BASE_URL", "")
    UNIQUE_MODEL_NAME: str = os.getenv("UNIQUE_MODEL_NAME", "")
    UNIQUE_APP_ID: str = os.getenv("UNIQUE_APP_ID", "")
    UNIQUE_APP_KEY: str = os.getenv("UNIQUE_APP_KEY", "")
    UNIQUE_COMPANY_ID: str = os.getenv("UNIQUE_COMPANY_ID", "")
    UNIQUE_USER_ID: str = os.getenv("UNIQUE_USER_ID", "")

    # Embedding model for semantic memory retrieval (vector similarity search).
    # Must support `embedContent` for the configured API key.
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "models/gemini-embedding-001")

    # ── Legacy JSON Memory Settings (DISABLED — kept for reference) ──────────
    # These paths were used by the old JSON-file memory backend. They are no
    # longer the active storage mechanism now that memory is persisted in MySQL.
    MEMORY_STORAGE_PATH: str = "data/memory/sessions.json"
    # Long-term memory store — episodic, semantic, and procedural records
    # per client, persisted across all sessions.
    LONG_TERM_MEMORY_PATH: str = "data/memory/long_term_memory.json"

    # ── MySQL Memory Database Settings (DISABLED — PostgreSQL is active) ─────────
    # MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    # MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", 3306))
    # MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    # MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    # MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "wealth_memory")

    # ── PostgreSQL Memory Database Settings (active) ─────────────────────────
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", 5432))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DATABASE: str = os.getenv("POSTGRES_DATABASE", "wealth_memory")
    # Optional: provide a full SQLAlchemy URL to override the parts above.
    MEMORY_DATABASE_URL_OVERRIDE: Optional[str] = os.getenv("MEMORY_DATABASE_URL")
    # Echo SQL statements to the logs (useful for debugging only).
    DB_ECHO: bool = os.getenv("DB_ECHO", "False").lower() in ("true", "1", "t")

    @property
    def MEMORY_DATABASE_URL(self) -> str:
        """Return the SQLAlchemy connection URL for the memory database."""
        if self.MEMORY_DATABASE_URL_OVERRIDE:
            return self.MEMORY_DATABASE_URL_OVERRIDE
        from urllib.parse import quote_plus
        password = quote_plus(self.POSTGRES_PASSWORD)
        # MYSQL_DISABLED — was: mysql+pymysql://{user}:{pw}@{host}:{port}/{db}?charset=utf8mb4
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DATABASE}"
        )
    
    # ── MCP (Model Context Protocol) Settings ───────────────────────────────
    # The Relationship Intelligence (CRM) agent connects to a *local* MCP
    # server over the streamable-http transport, discovers its tools at runtime,
    # and lets the LLM call them (true tool calling). If the server URL is not
    # set or the server is unreachable, the agent transparently falls back to
    # its built-in CRM tool, so the app keeps working without MCP configured.
    #
    # TODO: point MCP_CRM_SERVER_URL at your running MCP server, e.g.
    #       http://localhost:8002/mcp   (set it here or via the MCP_CRM_SERVER_URL env var / .env).
    MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "True").lower() in ("true", "1", "t")
    MCP_CRM_SERVER_URL: Optional[str] = os.getenv("MCP_CRM_SERVER_URL")  # e.g. "http://localhost:8002/mcp"
    MCP_TRANSPORT: str = os.getenv("MCP_TRANSPORT", "streamable_http")
    # How long (seconds) to wait when connecting / discovering tools before falling back.
    MCP_TIMEOUT: float = float(os.getenv("MCP_TIMEOUT", 15))
    # Safety cap on tool-call rounds per turn so a misbehaving model can't loop forever.
    MCP_MAX_TOOL_ITERATIONS: int = int(os.getenv("MCP_MAX_TOOL_ITERATIONS", 5))

    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_FILE_LOGGING: bool = os.getenv("ENABLE_FILE_LOGGING", "True").lower() in ("true", "1", "t")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")

    # CORS Settings (if needed in future)
    BACKEND_CORS_ORIGINS: list = ["*"]
    
    # Agent Configuration
    DEFAULT_AGENT_TIMEOUT: int = int(os.getenv("DEFAULT_AGENT_TIMEOUT", 60))  # seconds
    MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", 5))

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding='utf-8',
        case_sensitive=True,
        extra='ignore'
    )

settings = Settings()

