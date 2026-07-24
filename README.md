# Wealth Management Assistant — Helix

An intelligent **Agentic RAG** system powered by **LangGraph** and **Google Gemini** for wealth management advisory services. Features a real-time streaming chat UI, 4-way intent routing, conversation memory, and a companion CRM insights API backed by a synthetic SQLite database.

## 🌟 Features

- **Multi-Agent Orchestration**: LangGraph StateGraph with conditional entry-point routing
- **4-Way Intent Classification**: Routes queries to Portfolio Insights, Relationship Intelligence, General conversation, or Clarification
- **Real-Time Streaming (SSE)**: Server-Sent Events endpoint for token-by-token response rendering
- **Portfolio Insights Agent**: Analyzes portfolios, calculates metrics, provides data-backed recommendations in Indian notation (₹, lakhs/crores)
- **Relationship Intelligence Agent**: Tracks client engagement, sentiment, and CRM data
- **General & Clarification Agents**: Handles broad queries and asks focused follow-up questions when intent is ambiguous
- **Conversation Memory**: JSON-based session storage with multi-turn history injection
- **Chat UI**: Built-in HTML/CSS/JS chat interface with cache-busted assets
- **CRM Insights API**: Standalone FastAPI app (`crm_api.py`) serving customer overviews, portfolios, transactions, risk analysis from SQLite
- **Client Selector**: UI dropdown powered by `clients.json` for quick client switching
- **Health Monitoring**: Health, readiness, and liveness probes (Kubernetes-ready)
- **Security by Design**: Input validation, sanitization, global exception handler, and CORS

## 🏗️ Architecture

```
wealth_management_assistant/
├── main.py                  # Application entry point (FastAPI factory)
├── crm_api.py               # Standalone CRM insights API (SQLite-backed)
├── pyproject.toml            # Project metadata & dependencies (uv/pip)
├── app/
│   ├── config.py            # Pydantic Settings (env-driven)
│   ├── agents/
│   │   ├── base.py          # BaseAgent: shared LLM singleton + history helpers
│   │   ├── router.py        # RouterAgent: 4-way intent classification
│   │   ├── portfolio_insights.py        # PortfolioInsightsAgent
│   │   ├── relationship_intelligence.py # RelationshipIntelligenceAgent
│   │   ├── general.py       # GeneralAgent (conversational)
│   │   ├── clarification.py # ClarificationAgent
│   │   ├── graph.py         # LangGraph StateGraph with conditional entry point
│   │   ├── orchestrator.py  # process_chat() and stream_agent() entry points
│   │   ├── state.py         # TypedDict agent state definition
│   │   └── memory/
│   │       └── long_term_memory.py # Episodic / semantic / procedural / preferences
│   ├── prompts/
│   │   ├── portfolio_insights.py        # Portfolio Insights prompts
│   │   ├── relationship_intelligence.py # Relationship Intelligence prompts
│   │   ├── general.py       # General / conversational prompts
│   │   ├── clarification.py # Clarification prompts
│   │   ├── router.py        # Router / intent-classifier prompts
│   │   └── orchestrator.py  # Legacy orchestrator prompt (graph path)
│   ├── routes/
│   │   ├── agent.py         # /agent/chat, /agent/stream (SSE), /agent/clients, /agent/info
│   │   ├── ingest.py        # Document ingestion (placeholder)
│   │   ├── retrieve.py      # Retrieval (placeholder)
│   │   └── ui.py            # Serves chat UI at "/"
│   ├── schemas/
│   │   └── agent.py         # ChatRequest, ChatResponse, SessionInfo Pydantic models
│   ├── services/
│   │   ├── llm.py           # Google Gemini LLM initialization
│   │   ├── memory.py        # JSONMemoryService (session persistence)
│   │   ├── tools.py         # LangChain @tool definitions (portfolio, CRM, metrics, market)
│   │   └── ingestion.py     # Ingestion service (placeholder)
│   ├── static/              # app.js, style.css
│   ├── templates/           # index.html (chat shell)
│   └── utils/
│       ├── logger.py        # Rotating file + console logging
│       ├── helpers.py        # validate_session_id, sanitize_input
│       └── file_utils.py    # File operations
├── data/
│   ├── CRM/                 # SQLite DB + CSV seed data (customers, advisors, etc.)
│   ├── memory/              # Session memory (sessions.json)
│   ├── portfolio/           # clients.json, market.json
│   ├── uploads/             # User-uploaded documents
│   └── vectorstore/         # Vector store data
└── logs/                    # Rotating application logs
```

## 📋 Prerequisites

- **Python**: 3.14 or higher
- **Google Gemini API Key**: Get from [Google AI Studio](https://aistudio.google.com/)

## 🚀 Quick Start

### 1. Navigate to Project

```bash
cd wealth_management_assistant
```

### 2. Install Dependencies

Using `uv` (recommended):
```bash
uv sync
```

Or using `pip`:
```bash
pip install -e .
```

### 3. Configure Environment

Create a `.env` file:
```env
GOOGLE_API_KEY="your_actual_api_key_here"
```

### 4. Run the Application

```bash
python main.py
```

Or using `uv`:
```bash
uv run python main.py
```

The server will start on `http://0.0.0.0:8000` — open the chat UI at `http://localhost:8000/`

### 5. Run CRM Insights API (Optional)

```bash
uvicorn crm_api:app --port 8001
```

## 📡 API Endpoints

### System Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Chat UI (HTML) |
| `/health` | GET | Comprehensive health check |
| `/ready` | GET | Readiness probe |
| `/live` | GET | Liveness probe |
| `/api/docs` | GET | Swagger UI |
| `/api/redoc` | GET | ReDoc |

### Agent Endpoints (`/api/v1/agent`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/agent/stream` | POST | **Streaming chat** via SSE (primary) |
| `/api/v1/agent/chat` | POST | Non-streaming chat (compatibility) |
| `/api/v1/agent/info` | GET | App name, model, version for UI |
| `/api/v1/agent/clients` | GET | Client list for UI dropdown |
| `/api/v1/agent/sessions` | GET | List all sessions |
| `/api/v1/agent/sessions/{session_id}` | GET | Get session history |
| `/api/v1/agent/sessions/{session_id}` | DELETE | Delete a session |

### CRM API Endpoints (`crm_api.py` — port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | DB health + table counts |
| `/customer/{id}/overview` | GET | Customer AUM, accounts, segments |
| `/customer/{id}/interactions` | GET | Interaction history with sentiment |
| `/customer/{id}/portfolio` | GET | Holdings by asset class |
| `/customer/{id}/transactions` | GET | Recent transactions |
| `/customer/{id}/risk-analysis` | GET | Computed churn/risk level |
| `/customer/{id}/brief` | GET | Compact customer brief |

### Example: Streaming Chat (SSE)

```bash
curl -N -X POST "http://localhost:8000/api/v1/agent/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the current state of my portfolio?",
    "session_id": "user-123",
    "metadata": { "client_id": "C001" }
  }'
```

SSE event types: `step`, `token`, `done`, `error`

### Example: Non-Streaming Chat

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me client engagement summary",
    "session_id": "user-123",
    "metadata": { "client_id": "C001" }
  }'
```

## 🤖 Agents & Intent Routing

The LangGraph orchestrator classifies every user message into one of four intents:

| Intent | Agent | Description |
|--------|-------|-------------|
| `portfolio_insights` | Portfolio Insights | Investment analysis, metrics, rebalancing |
| `relationship_intelligence` | Relationship Intelligence | Client engagement, CRM data, sentiment |
| `general` | General Conversational | Broad finance questions, greetings |
| `needs_clarification` | Clarification | Ambiguous intent → asks a follow-up question |

## 🛠️ Tools

| Tool | Description | Used By |
|------|-------------|---------|
| `get_portfolio_summary` | Fetch portfolio holdings and valuations | Portfolio Insights |
| `calculate_portfolio_metrics` | Calculate returns, volatility, Sharpe ratio, alpha/beta | Portfolio Insights |
| `get_market_data` | Fetch current market prices for a symbol | Portfolio Insights |
| `get_client_engagement_history` | Fetch CRM meeting notes, sentiment, interactions | Relationship Intelligence |

## 📝 Configuration

All configuration via environment variables (`.env` file) managed by Pydantic Settings:

```env
# Application
APP_NAME="Wealth Management Assistant"
HOST="0.0.0.0"
PORT=8000
DEBUG=True
RELOAD=True

# Google Gemini
GOOGLE_API_KEY="your_api_key"
GEMINI_MODEL="gemini-1.5-pro"
GEMINI_TEMPERATURE=0.7
GEMINI_MAX_TOKENS=8192

# Memory
MEMORY_STORAGE_PATH="data/memory/sessions.json"

# Agent
DEFAULT_AGENT_TIMEOUT=30
MAX_AGENT_ITERATIONS=5

# Logging
LOG_LEVEL="INFO"
ENABLE_FILE_LOGGING=True
LOG_FILE="logs/app.log"
```

## 🔧 Development

### Adding New Agents

1. Create an agent module under `app/agents/` (e.g. `app/agents/my_agent.py`) with a class subclassing `BaseAgent` and a module-level singleton
2. Add its prompts as a dedicated module under `app/prompts/` (e.g. `app/prompts/my_agent.py`)
3. Register the node in `app/agents/graph.py`
4. Update router mapping in `graph.py` conditional entry point
5. Add streaming branch in `orchestrator.py` → `stream_agent()`
6. Add any specialized tools in `app/services/tools.py`

### Adding New Tools

1. Define tool in `app/services/tools.py` using `@tool` decorator
2. Import and invoke from the relevant agent module under `app/agents/`
3. Update agent prompts to reference the new tool capability

## 🧪 Testing

```bash
# Health check
curl http://localhost:8000/health

# Streaming chat
curl -N -X POST http://localhost:8000/api/v1/agent/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me my portfolio holdings", "session_id": "test-1", "metadata": {"client_id": "C001"}}'


## 📊 Memory Management

Sessions stored in JSON at `data/memory/sessions.json`. Conversation history is automatically:
- Saved after each user message and assistant response
- Injected into agent prompts (last 6 turns) for multi-turn context
- Trimmed for router prompts (last 3 turns) to keep classification fast

```json
{
  "user-123": {
    "history": [
      {"role": "user", "content": "What is my portfolio value?", "timestamp": "2024-01-20T10:30:00"},
      {"role": "assistant", "content": "Your portfolio is valued at ₹12,50,000", "timestamp": "2024-01-20T10:30:05"}
    ],
    "created_at": "2024-01-20T10:30:00",
    "last_updated": "2024-01-20T10:30:05"
  }
}
```


## 📈 Future Enhancements

- [ ] Database integration for memory (PostgreSQL/MongoDB)
- [ ] Real portfolio data integration (broker APIs)
- [ ] Connect CRM API tools to live SQLite database
- [ ] RAG with vector store for knowledge base documents
- [ ] Authentication & authorization
- [ ] Rate limiting
- [ ] WebSocket support for bidirectional streaming
- [ ] Multi-language support
- [ ] Real-time market data streaming
- [ ] Advanced analytics dashboard
