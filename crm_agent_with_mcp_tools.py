import asyncio
import json
import logging
import operator
import pprint
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, List, Any, Annotated
from langchain_google_genai import ChatGoogleGenerativeAI
from langfuse.langchain import CallbackHandler
from dotenv import load_dotenv
from langfuse import get_client
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)

langfuse = get_client()
 
# Verify connection
if langfuse.auth_check():
    print("Langfuse client is authenticated and ready!")
else:
    print("Authentication failed. Please check your credentials and host.")

# Initialize LLM
model = ChatGoogleGenerativeAI(model="gemini-2.5-flash",temperature=0)

mcp_client = MultiServerMCPClient(
        {
            "crm": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:9000/mcp",
                "headers": {"Accept": "text/event-stream"},
            }
        }
    )

async def load_crm_mcp_tools():
    return await mcp_client.get_tools()

tools = asyncio.run(load_crm_mcp_tools())
tools_by_name = {mcp_tool.name: mcp_tool for mcp_tool in tools}

model_with_tools = model.bind_tools(tools)

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

agent_builder.add_node(agent_node, "agent_node")
agent_builder.add_node(tool_node, "tool_node")

agent_builder.add_edge(START, "agent_node")
agent_builder.add_conditional_edges("agent_node", should_continue, ["tool_node", END])
agent_builder.add_edge("tool_node", "agent_node")

agent = agent_builder.compile()

# crm_agent_with_tools_structure = agent.get_graph()

# with open("crm_agent_with_tools_structure.png", "wb+") as f:
#     f.write(crm_agent_with_tools_structure.draw_mermaid_png())

langfuse_handler = CallbackHandler()

async def run_demo():
    user_query = [HumanMessage(content="Give me the overview, recent transactions and recent interactions of customer id 6?")]

    result = await agent.ainvoke(input={
        "messages": user_query
    }, config={"callbacks": [langfuse_handler]})

    # pprint.pprint(result)


if __name__ == "__main__":
    asyncio.run(run_demo())
