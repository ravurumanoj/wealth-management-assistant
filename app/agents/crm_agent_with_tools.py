import asyncio
import operator
import pprint
import requests
from fastapi import HTTPException
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List, Dict, Any, Annotated, Optional, Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler
from dotenv import load_dotenv
from langfuse import get_client
from langchain_core.tools import tool
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field

load_dotenv()

langfuse = get_client()
 
# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

# Initialize LLM
model = ChatGoogleGenerativeAI(model="gemini-2.5-flash",temperature=0)

@tool(name_or_callable='overview')
def get_customer_overview(customer_id: str) -> dict:
    """Fetches Overview of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/overview")
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Customer Overview for ID {customer_id}")
    
@tool(name_or_callable='interactions')
def get_customer_interactions(customer_id: str) -> dict:
    """Fetches Interactions of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/interactions")
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Customer Interactions for ID {customer_id}")
    
@tool(name_or_callable='portfolio')
def get_customer_portfolio(customer_id: str) -> dict:
    """Fetches Portfolio of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/portfolio")
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Customer Portfolio for ID {customer_id}")
    
@tool(name_or_callable='risk-analysis')
def get_customer_risk_analysis(customer_id: str) -> dict:
    """Fetches Risk Analysis of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/risk-analysis")
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Customer Risk Analysis for ID {customer_id}")
    
@tool(name_or_callable='brief')
def get_customer_brief(customer_id: str) -> dict:
    """Fetches Brief of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/brief")
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Customer Brief for ID {customer_id}")
    
@tool(name_or_callable='transactions')
def get_customer_transactions(customer_id: str) -> dict:
    """Fetches Transactions of the Customer based on given Customer ID"""
    response = requests.get(f"http://localhost:8000/customer/{customer_id}/transactions")
    if response.status_code == 200:
        return response.json()
    else:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Customer Transactions for ID {customer_id}")
    
# tools = ['brief', 'overview', 'interactions', 'transactions', 'risk-analysis', 'portfolio']
tools = [get_customer_brief, get_customer_overview, get_customer_interactions, get_customer_transactions, get_customer_risk_analysis, get_customer_portfolio]
tools_by_name = {tool.name: tool for tool in tools}

model_with_tools = model.bind_tools(tools)

# print(tools_by_name)
# print(model_with_tools)

class CRMAgentState(TypedDict):
    messages: Annotated[List[str], operator.add]

def agent_node(state: CRMAgentState):
    """LLM decides whether to call a tool or not"""
    return {
        "messages": [
            model_with_tools.invoke([
                SystemMessage(
                    content='You are an helpful CRM assistant equiped with a number of tools. Your task is to ' \
                    'assist financial advisor to understand more about customer based on the questions.'
                )
            ] + state["messages"])
        ]
    }

def tool_node(state: CRMAgentState):
    """Performs the tool call"""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))
    
    return {"messages": result}

def should_continue(state: CRMAgentState):
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "tool_node"

    return END

agent_builder = StateGraph(CRMAgentState)

agent_builder.add_node(agent_node, "agent_node")
agent_builder.add_node(tool_node, "tool_node")

agent_builder.add_edge(START, "agent_node")
agent_builder.add_conditional_edges("agent_node", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "agent_node")

agent = agent_builder.compile()

crm_agent_with_tools_structure = agent.get_graph()

with open("crm_agent_with_tools_structure.png", "wb+") as f:
    f.write(crm_agent_with_tools_structure.draw_mermaid_png())

langfuse_handler = CallbackHandler()

user_query = [HumanMessage(content="Give me the overview, recent transactions and recent interactions of customer id 6?")]

result = agent.invoke(input={
    "messages": user_query
}, config={"callbacks": [langfuse_handler]})
