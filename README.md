# wealth-management-assistant

Quick start (useful note about MCP):

- The project exposes a local CRM API via `crm_api.py` (FastAPI).
- A lightweight MCP server is implemented in `app/mcp_server.py` and exposes the CRM endpoints as tools.
- The agent in `app/agents/crm_agent_with_mcp.py` calls those tools via the in-process `mcp_client`.

To run the API and use the agent interactively:

1. Ensure dependencies are installed:

```powershell
pip install -r requirements.txt
```

2. Start the CRM API (this also allows the MCP tools to use the same DB):

```powershell
uvicorn crm_api:app --reload
```

3. Use the agent by running the `crm_agent_with_mcp.py` module or importing it in an interactive session. The MCP client calls are in-process and do not require a separate MCP server process.
