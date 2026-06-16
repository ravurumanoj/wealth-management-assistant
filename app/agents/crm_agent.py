import os
import requests
import operator
from fastapi import HTTPException
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from typing import TypedDict, List, Dict, Any, Annotated, Optional, Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler
from dotenv import load_dotenv
from langfuse import get_client
from langchain_core.tools import tool
from IPython.display import Image, display
from pydantic import BaseModel, Field
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.store.postgres import PostgresStore
from mem0 import MemoryClient
load_dotenv()

langfuse = get_client()
 
# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

# Initialize LLM
model = ChatGoogleGenerativeAI(model="gemini-2.5-flash",temperature=0)

Intent = Literal["interactions", "overview", "portfolio", "risk_profile", "transactions"]

class CRMAgentState(TypedDict):
    is_crm: bool
    user_query: str
    customer_id: str
    db_health: str
    user_intent: List[Intent]
    response: Annotated[list[str], operator.add]
    user_insights: str

class UserIntent(BaseModel):
    intent: List[Intent] = Field(..., description="List of user intents based on the query")

def check_db_health(state: CRMAgentState):
    '''Helpful in checking the DB Health before going to execute direct user request'''
    response = requests.get("http://localhost:8000/health")
    if response.status_code == 200:
        return {"db_health": "success"}
    else:
        return {"db_health": "failed"}

def get_customer_overview(state: CRMAgentState):
    '''Fetches the customer overview for a given customer_id'''
    customer_id = state["customer_id"]
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/overview")
    if response.status_code == 200:
        return {"response": [response.json()]}
    else:
        return {"response": [f"Failed to fetch customer overview for ID {customer_id}"]}
    
def get_customer_interactions(state: CRMAgentState):
    '''Fetches the customer interactions for a given customer_id'''
    customer_id = state["customer_id"]
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/interactions")
    if response.status_code == 200:
        return {"response": [response.json()]}
    else:
        return {"response": [f"Failed to fetch customer interactions for ID {customer_id}"]}
    
def get_customer_portfolio(state: CRMAgentState):
    '''Fetches the customer portfolio for a given customer_id'''
    customer_id = state["customer_id"]
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/portfolio")
    if response.status_code == 200:
        return {"response": [response.json()]}
    else:
        return {"response": [f"Failed to fetch customer portfolio for ID {customer_id}"]}

def get_customer_risk_profile(state: CRMAgentState):
    '''Fetches the customer risk profile for a given customer_id'''
    customer_id = state["customer_id"]
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/risk-analysis")
    if response.status_code == 200:
        return {"response": [response.json()]}
    else:
        return {"response": [f"Failed to fetch customer risk profile for ID {customer_id}"]}
    
def get_customer_brief(state: CRMAgentState):
    '''Fetches the customer brief for a given customer_id'''
    customer_id = state["customer_id"]
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/brief")
    if response.status_code == 200:
        return {"response": [response.json()]}
    else:
        return {"response": [f"Failed to fetch customer brief for ID {customer_id}"]}

def get_customer_transactions(state: CRMAgentState):
    '''Fetches the customer transactions for a given customer_id'''
    customer_id = state["customer_id"]
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/transactions")
    if response.status_code == 200:
        return {"response": [response.json()]}
    else:
        return {"response": [f"Failed to fetch customer transactions for ID {customer_id}"]}

def classify_query(state: CRMAgentState):
    user_query = state["user_query"]

    prompt = f"""You are a CRM assistant for a Wealth Management firm. Your task is to assist relationship managers in quickly 
    classifying the relevant tools about their customers based on their queries. You are provided with a set of tools that allow 
    you to classify about customers, such as their overview, interactions, portfolio, risk_profile and transactions.

    User Query: {user_query}

    Based on the user query, determine which tool(s) one or more you need to use to fetch the relevant information about the customer.
    """
    strucuture_model = model.with_structured_output(UserIntent)

    response = strucuture_model.invoke(prompt)

    return {"user_intent": response.intent}

def customer_insights(state: CRMAgentState):
    user_query = state["user_query"]
    tool_response = state["response"]

    prompt = f"""You are a CRM assistant for a Wealth Management firm. Your task is to assist relationship managers in quickly 
    providing insights about their customers based on their queries.

    User Query: {user_query}

    User Details: {tool_response}

    You must provide insights that would help the relationship manager only from the user query and the available information about the customer.
    """
    response = model.invoke(prompt)
    
    return {"user_insights": response.content}

def route_query(state: CRMAgentState) -> str:
    db_health = state["db_health"]
    if db_health == "success":
        return "success"
    else:
        return "failed"
    
def route_after_classify(state: CRMAgentState):
    user_intent = state["user_intent"]

    node_map = {
        "interactions": "get_customer_interactions",
        "portfolio": "get_customer_portfolio",
        "risk_profile": "get_customer_risk_profile",
        "transactions": "get_customer_transactions",
        "overview": "get_customer_overview"
    }

    sends = []

    for intent in user_intent:
        if intent in node_map:
            sends.append(Send(node_map[intent], state))

    return sends if sends else [Send("customer_insights", state)]

crm_graph = StateGraph(CRMAgentState)

crm_graph.add_node("check_db_health", check_db_health)
crm_graph.add_node("get_customer_brief", get_customer_brief)
crm_graph.add_node("classify_query", classify_query)
crm_graph.add_node("get_customer_overview", get_customer_overview)
crm_graph.add_node("get_customer_interactions", get_customer_interactions)
crm_graph.add_node("get_customer_portfolio", get_customer_portfolio)
crm_graph.add_node("get_customer_risk_profile", get_customer_risk_profile)
crm_graph.add_node("get_customer_transactions", get_customer_transactions)
crm_graph.add_node("customer_insights", customer_insights)

crm_graph.add_edge(START, "check_db_health")
crm_graph.add_conditional_edges("check_db_health", 
                               route_query,
                               {
                                   "success": "get_customer_brief",
                                    "failed": END
                                }
)
crm_graph.add_edge("get_customer_brief", "classify_query")
crm_graph.add_conditional_edges("classify_query", route_after_classify, ["get_customer_interactions", "get_customer_portfolio", 
                                                                         "get_customer_risk_profile", "get_customer_transactions", 
                                                                         "get_customer_overview", "customer_insights"])
crm_graph.add_edge("get_customer_overview", "customer_insights")
crm_graph.add_edge("get_customer_interactions", "customer_insights")
crm_graph.add_edge("get_customer_portfolio", "customer_insights")
crm_graph.add_edge("get_customer_risk_profile", "customer_insights")
crm_graph.add_edge("get_customer_transactions", "customer_insights")
crm_graph.add_edge("customer_insights", END)

crm_agent = crm_graph.compile()

crm_agent_structure = crm_agent.get_graph()

# with open("crm_agent_structure.png", "wb+") as f:
#     f.write(crm_agent_structure.draw_mermaid_png())

langfuse_handler = CallbackHandler()
result = crm_agent.invoke(input={
    "is_crm": True,
    "user_query": "What is the risk profile and recent transactions of customer 1?",
    "customer_id": 1
}, config={"callbacks": [langfuse_handler]})
