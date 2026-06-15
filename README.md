# Wealth Management Assistant

An intelligent **Agentic RAG** system powered by **LangGraph** and **Google Gemini** for wealth management advisory services.

## 🌟 Features

- **Multi-Agent Orchestration**: LangGraph-based orchestrator managing specialized agents
- **Portfolio Insights Agent**: Analyzes portfolios, investments, and market trends
- **Relationship Intelligence Agent**: Tracks client engagement and relationship health
- **Session Memory Management**: JSON-based session storage (easily upgradeable to DB)
- **RESTful API**: FastAPI backend with comprehensive endpoints
- **Health Monitoring**: Built-in health check and readiness probes
- **Comprehensive Logging**: File and console logging with rotation
- **Security by Design**: Input validation, sanitization, and error handling

## 🏗️ Architecture

```
wealth_management_assistant/
├── app/
│   ├── agents/          # LangGraph agent nodes and orchestrator
│   │   ├── graph.py     # LangGraph workflow definition
│   │   ├── nodes.py     # Agent node implementations
│   │   ├── orchestrator.py  # Main orchestration logic
│   │   └── state.py     # Agent state management
│   ├── prompts/         # Agent system prompts
│   ├── routes/          # FastAPI route handlers
│   ├── schemas/         # Pydantic models
│   ├── services/        # Core services (LLM, memory, tools)
│   ├── utils/           # Utility functions
│   └── config.py        # Application configuration
├── data/                # Data storage
│   └── memory/          # Session memory storage
├── logs/                # Application logs
└── main.py              # Application entry point
```

## 📋 Prerequisites

- **Python**: 3.14 or higher
- **Google Gemini API Key**: Get from [Google AI Studio](https://aistudio.google.com/)

## 🚀 Quick Start

### 1. Clone or Navigate to Project

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

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` and add your Google API key:
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

The server will start on `http://0.0.0.0:8000`

## 📡 API Endpoints

### System Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Root endpoint with app info |
| `/health` | GET | Comprehensive health check |
| `/ready` | GET | Readiness probe |
| `/live` | GET | Liveness probe |
| `/api/docs` | GET | Interactive API documentation (Swagger) |
| `/api/redoc` | GET | Alternative API documentation (ReDoc) |

### Agent Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/agent/chat` | POST | Chat with the assistant |
| `/api/v1/agent/sessions` | GET | List all sessions |
| `/api/v1/agent/sessions/{session_id}` | GET | Get session history |
| `/api/v1/agent/sessions/{session_id}` | DELETE | Delete a session |

### Example: Chat Request

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the current state of my portfolio?",
    "session_id": "user-123",
    "metadata": {
      "client_id": "CLIENT001"
    }
  }'
```

### Example: Get Sessions

```bash
curl "http://localhost:8000/api/v1/agent/sessions"
```

## 🤖 Agents

### 1. Portfolio Insights Agent

**Responsibilities:**
- Analyze investment portfolios
- Evaluate risk profiles and asset allocation
- Monitor market trends
- Suggest rebalancing strategies
- Calculate portfolio metrics (returns, volatility, ratios)

**Keywords that trigger this agent:**
- portfolio, stock, market, investment, holdings, asset

### 2. Relationship Intelligence Agent

**Responsibilities:**
- Track client engagement history
- Analyze client preferences and satisfaction
- Provide relationship health insights
- Suggest communication strategies
- Monitor meeting notes and action items

**Keywords that trigger this agent:**
- client, meeting, engagement, relationship, satisfaction

## 🛠️ Tools

Each agent has access to specialized tools:

| Tool | Description | Used By |
|------|-------------|---------|
| `get_portfolio_summary` | Fetch portfolio holdings and valuations | Portfolio Insights |
| `calculate_portfolio_metrics` | Calculate returns, risk metrics | Portfolio Insights |
| `get_market_data` | Fetch current market prices | Portfolio Insights |
| `get_client_engagement_history` | Fetch meeting notes and interactions | Relationship Intelligence |

**Note**: Currently using dummy data. Replace with real integrations in production.

## 📝 Configuration

All configuration is managed via environment variables (`.env` file):

```env
# Application
APP_NAME="Wealth Management Assistant"
HOST="0.0.0.0"
PORT=8000
DEBUG=True

# Google Gemini
GOOGLE_API_KEY="your_api_key"
GEMINI_MODEL="gemini-1.5-pro"
GEMINI_TEMPERATURE=0.7

# Memory
MEMORY_STORAGE_PATH="data/memory/sessions.json"

# Logging
LOG_LEVEL="INFO"
ENABLE_FILE_LOGGING=True
LOG_FILE="logs/app.log"
```

## 🔧 Development

### Project Structure Details

- **`app/agents/`**: Contains LangGraph agent definitions
  - `graph.py`: Defines the agent workflow graph
  - `nodes.py`: Implements agent node logic
  - `orchestrator.py`: Main orchestration entry point
  - `state.py`: TypedDict state definition

- **`app/services/`**: Core business logic
  - `llm.py`: Gemini LLM initialization
  - `memory.py`: Session memory management
  - `tools.py`: Agent tools

- **`app/utils/`**: Reusable utilities
  - `logger.py`: Logging configuration
  - `helpers.py`: Common helper functions
  - `file_utils.py`: File operations

### Adding New Agents

1. Add agent node to `app/agents/nodes.py`
2. Update the workflow graph in `app/agents/graph.py`
3. Add routing logic in the `router_node`
4. Create agent prompts in `app/prompts/agent_prompts.py`
5. Add any specialized tools in `app/services/tools.py`

### Adding New Tools

1. Define tool in `app/services/tools.py` using `@tool` decorator
2. Add tool to the `tools` list
3. Update agent prompts to reference the new tool

## 🧪 Testing

Test the health endpoint:
```bash
curl http://localhost:8000/health
```

Test chat functionality:
```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me my portfolio holdings",
    "session_id": "test-session-1"
  }'
```

## 📊 Memory Management

Sessions are stored in JSON format at `data/memory/sessions.json`:

```json
{
  "user-123": {
    "history": [
      {
        "role": "user",
        "content": "What is my portfolio value?",
        "timestamp": "2024-01-20T10:30:00"
      },
      {
        "role": "assistant",
        "content": "Your portfolio is valued at ₹12,50,000",
        "timestamp": "2024-01-20T10:30:05"
      }
    ],
    "created_at": "2024-01-20T10:30:00",
    "last_updated": "2024-01-20T10:30:05"
  }
}
```

**Future Enhancement**: Replace with database storage (PostgreSQL, MongoDB, etc.)

## 🔐 Security Features

- **Input Validation**: Session IDs and user inputs are validated
- **Input Sanitization**: Removes harmful characters from user inputs
- **Error Handling**: Comprehensive error handling with proper HTTP status codes
- **Logging**: All operations are logged for audit trails
- **CORS**: Configurable CORS settings

## 🚢 Deployment

### Running on Network

The app runs on `0.0.0.0` by default, allowing access via:
- `http://localhost:8000`
- `http://<your-ip-address>:8000`

### Docker (Future)

```dockerfile
FROM python:3.14-slim
WORKDIR /app
COPY . .
RUN pip install -e .
CMD ["python", "main.py"]
```

### Environment Variables for Production

```env
DEBUG=False
LOG_LEVEL="WARNING"
HOST="0.0.0.0"
PORT=8000
```

## 📈 Future Enhancements

- [ ] Database integration for memory (PostgreSQL/MongoDB)
- [ ] Real portfolio data integration (broker APIs)
- [ ] Real CRM integration
- [ ] Vector store for RAG (knowledge base)
- [ ] Authentication & authorization
- [ ] Rate limiting
- [ ] Async tool execution
- [ ] Multi-language support
- [ ] Real-time market data streaming
- [ ] Advanced analytics dashboard

## 🤝 Contributing

1. Create feature branch
2. Make changes
3. Test thoroughly
4. Submit pull request

## 📄 License

Proprietary - Internal Use Only

## 📞 Support

For questions or issues, please contact the development team.

---

**Built with ❤️ using FastAPI, LangGraph, and Google Gemini**