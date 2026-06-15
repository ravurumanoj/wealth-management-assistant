# API Usage Guide

## Wealth Management Assistant API Documentation

This guide provides detailed examples for using the Wealth Management Assistant API.

## Base URL

```
http://localhost:8000
```

For network access:
```
http://<your-ip-address>:8000
```

## Authentication

Currently, no authentication is required. This will be added in future versions.

## Content Type

All requests and responses use `application/json`.

---

## System Endpoints

### 1. Root Endpoint

**GET** `/`

Get basic application information.

**Response:**
```json
{
  "app": "Wealth Management Assistant",
  "version": "1.0.0",
  "status": "running",
  "timestamp": "2024-01-20T10:30:00.000000",
  "documentation": "http://localhost:8000/api/docs"
}
```

### 2. Health Check

**GET** `/health`

Comprehensive health check with all system statuses.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-20T10:30:00.000000",
  "version": "1.0.0",
  "checks": {
    "api": "ok",
    "llm_configured": "ok",
    "memory_system": "ok",
    "python_version": "3.14.0"
  }
}
```

### 3. Readiness Probe

**GET** `/ready`

Simple readiness check for container orchestration.

**Response:**
```json
{
  "ready": true
}
```

### 4. Liveness Probe

**GET** `/live`

Simple liveness check for container orchestration.

**Response:**
```json
{
  "live": true
}
```

---

## Agent Endpoints

### 1. Chat with Agent

**POST** `/api/v1/agent/chat`

Send a message to the wealth management assistant.

**Request Body:**
```json
{
  "message": "What is the current value of my portfolio?",
  "session_id": "user-123",
  "metadata": {
    "client_id": "CLIENT001",
    "user_name": "John Doe"
  }
}
```

**Fields:**
- `message` (required): User's question or request
- `session_id` (required): Unique session identifier (alphanumeric, hyphens, underscores)
- `metadata` (optional): Additional context (client_id, preferences, etc.)

**Response:**
```json
{
  "session_id": "user-123",
  "response": "Portfolio Insights: I've analyzed your query. Your portfolio shows strong diversification with holdings in RELIANCE, TCS, HDFC, INFY. Total value: ₹12,50,000. Watch out for volatility in tech stocks.",
  "agent_used": "portfolio_insights"
}
```

**Example with cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me my portfolio summary",
    "session_id": "user-123",
    "metadata": {
      "client_id": "CLIENT001"
    }
  }'
```

**Example with Python:**
```python
import requests

url = "http://localhost:8000/api/v1/agent/chat"
payload = {
    "message": "What is my portfolio value?",
    "session_id": "user-123",
    "metadata": {
        "client_id": "CLIENT001"
    }
}

response = requests.post(url, json=payload)
print(response.json())
```

**Example with JavaScript:**
```javascript
fetch('http://localhost:8000/api/v1/agent/chat', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: 'Analyze my portfolio',
    session_id: 'user-123',
    metadata: {
      client_id: 'CLIENT001'
    }
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

---

### 2. List All Sessions

**GET** `/api/v1/agent/sessions`

Retrieve all chat sessions with metadata.

**Response:**
```json
[
  {
    "session_id": "user-123",
    "created_at": "2024-01-20T09:00:00.000000",
    "last_updated": "2024-01-20T10:30:00.000000",
    "history_count": 12
  },
  {
    "session_id": "user-456",
    "created_at": "2024-01-19T14:00:00.000000",
    "last_updated": "2024-01-19T15:00:00.000000",
    "history_count": 8
  }
]
```

**Example:**
```bash
curl "http://localhost:8000/api/v1/agent/sessions"
```

---

### 3. Get Session History

**GET** `/api/v1/agent/sessions/{session_id}`

Retrieve complete chat history for a specific session.

**Response:**
```json
{
  "session_id": "user-123",
  "history": [
    {
      "role": "user",
      "content": "What is my portfolio value?",
      "timestamp": "2024-01-20T10:00:00.000000"
    },
    {
      "role": "assistant",
      "content": "Your portfolio is valued at ₹12,50,000",
      "timestamp": "2024-01-20T10:00:05.000000"
    },
    {
      "role": "user",
      "content": "When was my last meeting?",
      "timestamp": "2024-01-20T10:05:00.000000"
    },
    {
      "role": "assistant",
      "content": "Your last meeting was on 2024-01-15",
      "timestamp": "2024-01-20T10:05:03.000000"
    }
  ]
}
```

**Example:**
```bash
curl "http://localhost:8000/api/v1/agent/sessions/user-123"
```

---

### 4. Delete Session

**DELETE** `/api/v1/agent/sessions/{session_id}`

Delete a session and all its history.

**Response:**
```json
{
  "message": "Session 'user-123' deleted successfully"
}
```

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/agent/sessions/user-123"
```

---

## Agent Routing

The orchestrator automatically routes queries to the appropriate agent based on keywords:

### Portfolio Insights Agent

**Triggered by keywords:**
- portfolio, stock, market, investment, holdings, asset, equity, mutual fund, returns, performance

**Example queries:**
- "What is my portfolio value?"
- "Show me my stock holdings"
- "How is the market performing?"
- "Analyze my investment returns"

### Relationship Intelligence Agent

**Triggered by keywords:**
- client, meeting, engagement, relationship, satisfaction, interaction, notes, communication

**Example queries:**
- "When was my last meeting?"
- "What is my client satisfaction score?"
- "Show my engagement history"
- "What were the notes from my last interaction?"

---

## Error Responses

### 400 Bad Request

Invalid input or validation error.

```json
{
  "detail": "Invalid session ID format. Use alphanumeric characters, hyphens, or underscores."
}
```

### 404 Not Found

Resource not found.

```json
{
  "detail": "Session 'invalid-session' not found"
}
```

### 500 Internal Server Error

Server error.

```json
{
  "detail": "An error occurred while processing your request. Please try again."
}
```

---

## Session ID Guidelines

- **Format**: Alphanumeric with optional hyphens and underscores
- **Max Length**: 100 characters
- **Valid Examples**: 
  - `user-123`
  - `session_abc_def`
  - `client-001-2024`
- **Invalid Examples**:
  - `user@123` (contains @)
  - `user 123` (contains space)
  - Empty string

---

## Complete Workflow Example

### 1. Start a new conversation

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me my portfolio",
    "session_id": "demo-session-001"
  }'
```

### 2. Continue the conversation

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What about my client meetings?",
    "session_id": "demo-session-001"
  }'
```

### 3. View conversation history

```bash
curl "http://localhost:8000/api/v1/agent/sessions/demo-session-001"
```

### 4. Clean up (delete session)

```bash
curl -X DELETE "http://localhost:8000/api/v1/agent/sessions/demo-session-001"
```

---

## Interactive API Documentation

Visit the following URLs for interactive API documentation:

- **Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`

These interfaces allow you to:
- View all endpoints
- See request/response schemas
- Test API calls directly from the browser
- Download OpenAPI specification

---

## Rate Limiting

Currently, no rate limiting is implemented. This will be added in future versions.

---

## Best Practices

1. **Session Management**
   - Use unique session IDs for different users/conversations
   - Clean up old sessions periodically
   - Include relevant metadata for better context

2. **Error Handling**
   - Always check response status codes
   - Implement retry logic for 5xx errors
   - Validate session IDs before sending requests

3. **Performance**
   - Keep messages concise for faster processing
   - Use metadata to provide context instead of long messages
   - Monitor session history size

4. **Security**
   - Sanitize user inputs before sending
   - Don't include sensitive data in session IDs
   - Use HTTPS in production

---

## Support

For questions or issues, check the logs at `logs/app.log` or contact the development team.
