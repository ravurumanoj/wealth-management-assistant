import asyncio
import json
import logging
import operator
import pprint
import os
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List, Any, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langfuse.langchain import CallbackHandler
from dotenv import load_dotenv
from langfuse import get_client
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_google_community import GmailToolkit
from langgraph.checkpoint.memory import InMemorySaver
from langchain_chroma import Chroma

load_dotenv()

logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)

langfuse = get_client()
 
# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

# Initialize LLM
model = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite",temperature=0)

embedding_model = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

PERSIST_DIR = "./tools_chroma_db"
COLLECTION_NAME = "tool_vectors"

mcp_client = MultiServerMCPClient(
        {
            "crm": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8080/mcp",
                "headers": {"Accept": "text/event-stream"},
            }
        }
    )

async def load_crm_mcp_tools():
    return await mcp_client.get_tools()

# Refer Below links to setup Gmail MCP and Toolkit
# https://docs.langchain.com/oss/python/integrations/tools/google_gmail
# https://developers.google.com/workspace/gmail/api/guides/configure-mcp-server

gmail_tools = GmailToolkit().get_tools()

tools = asyncio.run(load_crm_mcp_tools()) + gmail_tools
tools_by_name = {mcp_tool.name: mcp_tool for mcp_tool in tools}

# tools_by_desc = {mcp_tool.name: mcp_tool.description for mcp_tool in tools}
# pprint.pprint(tools_by_desc)

if not os.path.exists(PERSIST_DIR):
    tool_vector_store = Chroma.from_texts(texts=[mcp_tool.description for mcp_tool in tools], 
                                          metadatas=[{"name": mcp_tool.name} for mcp_tool in tools], 
                                          collection_name=COLLECTION_NAME, 
                                          embedding=embedding_model, 
                                          persist_directory=PERSIST_DIR)
else:
    tool_vector_store = Chroma(embedding_function=embedding_model, collection_name=COLLECTION_NAME, persist_directory=PERSIST_DIR)

def mcp_tool_filtering(state: CRMAgentState):
    """Filters the MCP tools semantically for the user query."""
    user_query = state["messages"][0].content
    # tool_with_score = tool_vector_store.similarity_search_with_relevance_scores(user_query, k=15)
    # print(tool_with_score)
    tool_retriever = tool_vector_store.as_retriever()
    filtered_tools = [tool.metadata.get("name") for tool in tool_retriever.invoke(user_query)]

    return {"tools_to_use": filtered_tools}

def get_model_with_filtered_tools(state: CRMAgentState):
    """Bind the model to only the tools that match the current query."""
    selected_tools = [tools_by_name[name] for name in state.get("tools_to_use", []) if name in tools_by_name]
    if not selected_tools:
        selected_tools = tools

    return model.bind_tools(selected_tools)

# print(tools_by_name)
# print(model_with_tools)

def call_crm_mcp_tool(tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    async def _call():
        async with mcp_client.session("crm") as session:
            result = await session.call_tool(tool_name, arguments or {})
            if getattr(result, "isError", False):
                raise RuntimeError(f"MCP tool error: {result}")
            if hasattr(result, "structuredContent") and result.structuredContent is not None:
                return result.structuredContent
            if hasattr(result, "output"):
                return result.output
            if hasattr(result, "content"):
                return result.content
            return result

    return asyncio.run(_call())


class CRMAgentState(TypedDict):
    messages: Annotated[List[Any], operator.add]
    tools_to_use: List[Any]

def agent_node(state: CRMAgentState):
    """LLM decides whether to call a tool or not."""
    model_with_filtered_tools = get_model_with_filtered_tools(state)
    return {
        "messages": [
            model_with_filtered_tools.invoke([
                SystemMessage(
                    content='You are an helpful CRM assistant equiped with a number of tools. Your task is to ' \
                    'assist financial advisor to understand more about customer based on the questions.'
                )
            ] + state["messages"])
        ]
    }

async def tool_node(state: CRMAgentState):
    """Performs the tool call"""
    result = []
    for tool_call in state["messages"][-1].tool_calls:
        tool_name = tool_call["name"]
        tool = tools_by_name[tool_name]
        observation = await tool.ainvoke(tool_call["args"] or {})
        if isinstance(observation, (dict, list)):
            content = json.dumps(observation, indent=2, default=str)
        else:
            content = str(observation)
        result.append(ToolMessage(content=content, tool_call_id=tool_call["id"]))
    
    return {"messages": result}

def should_continue(state: CRMAgentState):
    """Decide if we should continue the loop or stop based upon whether the LLM made a tool call"""

    messages = state["messages"]
    last_message = messages[-1]

    if last_message.tool_calls:
        return "tool_node"

    return END

agent_builder = StateGraph(CRMAgentState)

agent_builder.add_node(mcp_tool_filtering, "mcp_tool_filtering")
agent_builder.add_node(agent_node, "agent_node")
agent_builder.add_node(tool_node, "tool_node")

agent_builder.add_edge(START, "mcp_tool_filtering")
agent_builder.add_edge("mcp_tool_filtering", "agent_node")
agent_builder.add_conditional_edges("agent_node", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "agent_node")

agent = agent_builder.compile(checkpointer=InMemorySaver())

# crm_agent_with_tools_structure = agent.get_graph()

# with open("crm_agent_with_tools_structure.png", "wb+") as f:
#     f.write(crm_agent_with_tools_structure.draw_mermaid_png())

langfuse_handler = CallbackHandler()

async def run_demo():
    user_query = [HumanMessage(content="Draft an email with the overview, recent transactions and interactions of customer id 8?")]

    result = await agent.ainvoke(input={
        "messages": user_query
    }, config={"callbacks": [langfuse_handler], "configurable": {"thread_id": "harichandar_07"}})

    # pprint.pprint(result)


if __name__ == "__main__":
    asyncio.run(run_demo())
