# Quick Start Guide

Get your Wealth Management Assistant running in 5 minutes!

## Prerequisites Check

Before starting, ensure you have:
- ✅ Python 3.14 or higher
- ✅ Google Gemini API key ([Get it here](https://aistudio.google.com/))
- ✅ Terminal/Command Prompt access

## Step-by-Step Setup

### Step 1: Navigate to Project Directory

```bash
cd wealth_management_assistant
```

### Step 2: Install Dependencies

Choose one of the following methods:

**Option A: Using uv (Recommended - Faster)**
```bash
uv sync
```

**Option B: Using pip**
```bash
pip install -e .
```

This will install all required packages including:
- FastAPI
- LangGraph
- LangChain
- Google Generative AI
- And more...

### Step 3: Configure Environment

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Open `.env` in your favorite editor:
```bash
# Windows
notepad .env

# Mac/Linux
nano .env
```

3. Update the `GOOGLE_API_KEY` with your actual API key:
```env
GOOGLE_API_KEY="your_actual_google_api_key_here"
```

Save and close the file.

### Step 4: Run the Application

```bash
python main.py
```

You should see output like:
```
INFO - Starting Wealth Management Assistant v1.0.0
INFO - Server running on 0.0.0.0:8000
INFO - API documentation available at http://0.0.0.0:8000/api/docs
```

### Step 5: Test the Application

Open a new terminal and test with:

```bash
curl http://localhost:8000/health
```

You should see:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-20T10:30:00",
  "version": "1.0.0",
  "checks": {
    "api": "ok",
    "llm_configured": "ok",
    "memory_system": "ok",
    "python_version": "3.14.0"
  }
}
```

## First Chat Request

Try your first chat interaction:

```bash
curl -X POST "http://localhost:8000/api/v1/agent/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is my portfolio value?",
    "session_id": "quickstart-test"
  }'
```

Expected response:
```json
{
  "session_id": "quickstart-test",
  "response": "Portfolio Insights: I've analyzed your query...",
  "agent_used": "portfolio_insights"
}
```

## Accessing the API Documentation

Open your browser and visit:
- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

You can test all APIs interactively from these pages!

## Accessing from Another Device

To access from another device on the same network:

1. Find your IP address:

**Windows:**
```bash
ipconfig
```
Look for "IPv4 Address" (e.g., 192.168.1.100)

**Mac/Linux:**
```bash
ifconfig
```
or
```bash
hostname -I
```

2. Access from another device:
```
http://192.168.1.100:8000
```

## Common Issues & Solutions

### Issue 1: Port Already in Use

**Error:** `Address already in use`

**Solution:** Change the port in `.env`:
```env
PORT=8001
```

### Issue 2: Google API Key Not Working

**Error:** `GOOGLE_API_KEY is not configured`

**Solution:** 
1. Make sure you copied `.env.example` to `.env`
2. Replace `your_google_api_key_here` with your actual key
3. Remove quotes if they're causing issues
4. Restart the application

### Issue 3: Module Not Found

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:** 
```bash
pip install -e .
```

### Issue 4: Permission Denied on Logs

**Error:** `Permission denied: logs/app.log`

**Solution:**
```bash
# Create logs directory manually
mkdir logs

# Or disable file logging in .env
ENABLE_FILE_LOGGING=False
```

## Next Steps

Now that your app is running:

1. **Explore the API**: Use the Swagger UI at `/api/docs`
2. **Read the Full Documentation**: Check [README.md](README.md)
3. **Learn the API**: Review [API_GUIDE.md](API_GUIDE.md)
4. **Customize Agents**: Modify agents in `app/agents/nodes.py`
5. **Add Real Data**: Replace dummy tools in `app/services/tools.py`

## Stopping the Application

Press `Ctrl+C` in the terminal running the application.

## What's Next?

- **Add Database**: Replace JSON memory with PostgreSQL/MongoDB
- **Integrate Real Data**: Connect to portfolio APIs and CRM systems
- **Add Authentication**: Implement JWT-based auth
- **Deploy to Cloud**: Deploy to AWS, Azure, or GCP

## Need Help?

- Check the logs: `logs/app.log`
- Review error messages carefully
- Ensure your Google API key is valid
- Make sure port 8000 is not blocked by firewall

---

**Congratulations! 🎉** Your Wealth Management Assistant is now running!
