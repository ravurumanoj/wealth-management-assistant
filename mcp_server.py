from fastmcp import FastMCP
from mcp.types import ToolAnnotations
import requests
import os
import uvicorn
from fastapi import HTTPException
from typing import List
from dotenv import load_dotenv
from mcp_middleware import MCPAuthMiddleware

load_dotenv()

API_TOKEN = os.environ.get("API_TOKEN")

headers = {
    "Authorization": f"Bearer {API_TOKEN}"
}

def get_crm_health() -> dict:
    """Checks the health of the CRM database"""
    response = requests.get("http://localhost:8000/health", headers=headers)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to retrieve CRM health information")
    return response.json()

def get_customer_overview(customer_id: str) -> dict:
    """Fetches Overview of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/overview", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch Customer Overview for ID {customer_id}")
    
def get_customer_interactions(customer_id: str) -> List[dict]:
    """Fetches Interactions of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/interactions", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch Customer Interactions for ID {customer_id}")

def get_customer_portfolio(customer_id: str) -> List[dict]:
    """Fetches Portfolio of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/portfolio", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch Customer Portfolio for ID {customer_id}")

def get_customer_risk_analysis(customer_id: str) -> dict:
    """Fetches Risk Analysis of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/risk-analysis", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch Customer Risk Analysis for ID {customer_id}")
    
def get_customer_brief(customer_id: str) -> dict:
    """Fetches Brief of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/brief", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch Customer Brief for ID {customer_id}")

def get_customer_transactions(customer_id: str) -> List[dict]:
    """Fetches Transactions of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/transactions", headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=response.status_code, detail=f"Failed to fetch Customer Transactions for ID {customer_id}")
    

app = FastMCP(name="crm_mcp_server")

asgi_app = app.http_app()

asgi_app.add_middleware(MCPAuthMiddleware)

app.tool(get_crm_health, name="health", description="Check CRM database health", 
         annotations=ToolAnnotations(title="crm_health", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
app.tool(get_customer_overview, name="customer_overview", description="Get customer overview", 
         annotations=ToolAnnotations(title="crm_customer_overview", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False))
app.tool(get_customer_interactions, name="customer_interactions", description="Get customer interactions")
app.tool(get_customer_portfolio, name="customer_portfolio", description="Get customer portfolio")
app.tool(get_customer_transactions, name="customer_transactions", description="Get customer transactions")
app.tool(get_customer_risk_analysis, name="customer_risk", description="Get customer risk profile")
app.tool(get_customer_brief, name="customer_brief", description="Get customer brief")


if __name__ == "__main__":
    # app.run(transport="streamable-http", host="127.0.0.1", port=9000)
    uvicorn.run(asgi_app, host="127.0.0.1", port=9000)
