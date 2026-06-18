from fastmcp import FastMCP

import crm_api


def health_tool() -> dict:
    return crm_api.health()


def customer_overview_tool(customer_id: int) -> dict:
    return crm_api.customer_overview(customer_id)


def customer_interactions_tool(customer_id: int, limit: int = 20) -> list[dict]:
    return crm_api.customer_interactions(customer_id, limit)


def customer_portfolio_tool(customer_id: int) -> list[dict]:
    return crm_api.customer_portfolio(customer_id)


def customer_transactions_tool(customer_id: int, limit: int = 20) -> list[dict]:
    return crm_api.customer_transactions(customer_id, limit)


def customer_risk_tool(customer_id: int) -> dict:
    return crm_api.customer_risk(customer_id)


def customer_brief_tool(customer_id: int) -> dict:
    return crm_api.customer_brief(customer_id)


app = FastMCP(name="crm_mcp_server")

app.tool(health_tool, name="health", description="Check CRM database health")
app.tool(customer_overview_tool, name="customer_overview", description="Get customer overview")
app.tool(customer_interactions_tool, name="customer_interactions", description="Get customer interactions")
app.tool(customer_portfolio_tool, name="customer_portfolio", description="Get customer portfolio")
app.tool(customer_transactions_tool, name="customer_transactions", description="Get customer transactions")
app.tool(customer_risk_tool, name="customer_risk", description="Get customer risk profile")
app.tool(customer_brief_tool, name="customer_brief", description="Get customer brief")


if __name__ == "__main__":
    app.run(transport="streamable-http", host="127.0.0.1", port=9000)
