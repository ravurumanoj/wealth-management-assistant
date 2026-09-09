"""Relationship Intelligence agent (the "CRM agent").

Discovers MCP CRM tools at runtime, runs LLM-driven tool calling, and returns
raw tool results. Final response generation is handled by SynthesizerAgent.

Graph entry point : run(state)          -> stores results in state["crm_output"]
Streaming helper  : collect_data(state) -> returns the raw data dict directly
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool

from app.agents.base import BaseAgent, extract_text
from app.agents.memory import long_term_memory  # noqa: F401  # LTM_DISABLED
from app.agents.state import AgentState
from app.config import settings
from app.prompts.relationship_intelligence import (
    CRM_TOOL_COLLECTION_SUFFIX,
    RELATIONSHIP_INTELLIGENCE_SYSTEM_PROMPT,
    RELATIONSHIP_INTELLIGENCE_USER_TEMPLATE,
)
from app.services.crm_api_tools import CRM_TOOLS
from app.services.mcp_client import get_mcp_tools
from app.utils.logger import logger


class RelationshipIntelligenceAgent(BaseAgent):
    """CRM data collector -- discovers MCP tools, fetches results, no LLM generation."""

    async def _load_tools(self) -> Tuple[List[BaseTool], Dict[str, BaseTool]]:
        """Discover MCP CRM tools, falling back to built-in CRM tools. Never raises."""
        tools: List[BaseTool] = []
        try:
            tools = await get_mcp_tools()
        except Exception as e:
            logger.warning(f"_load_tools: MCP discovery raised ({e}); no MCP CRM tools this turn.")
        # Fall back to the built-in local CRM tools when no MCP server is configured/available.
        if not tools:
            tools = list(CRM_TOOLS)
            logger.info("CRMAgent: using built-in local CRM tools (no MCP server available)")
        tool_map = {t.name: t for t in tools}
        logger.info(f"CRMAgent: {len(tools)} CRM tool(s) loaded")
        return tools, tool_map

    def _build_tool_messages(
        self,
        user_msg: str,
        client_id: str,
        history: Optional[List[dict]] = None,
        summary: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> List[BaseMessage]:
        """Build the initial message list that primes the LLM to call tools.

        ``extra_context`` carries upstream producer output (sequential execution)
        or a re-fetch instruction (replan loop) and is appended to the context.
        """
        additional_context = (
            f"Client ID: {client_id}\n"
            f"Pass customer_id = '{client_id}' to all CRM tools."
        )
        if extra_context:
            additional_context += f"\n\n{extra_context}"
        user_prompt = RELATIONSHIP_INTELLIGENCE_USER_TEMPLATE.format(
            user_message=user_msg + CRM_TOOL_COLLECTION_SUFFIX,
            additional_context=additional_context,
        )
        history_msgs = self._format_history(history or [], summary=summary)
        msgs: List[BaseMessage] = [SystemMessage(content=RELATIONSHIP_INTELLIGENCE_SYSTEM_PROMPT)]
        # LTM_DISABLED — uncomment when embeddings are available on this machine
        # try:
        #     lt_ctx = long_term_memory.format_long_term_context(client_id, user_msg)
        #     if lt_ctx:
        #         msgs.append(SystemMessage(content=lt_ctx))
        # except Exception:
        #     logger.warning("_build_tool_messages: long-term memory load failed (non-fatal)")
        msgs.extend(history_msgs)
        msgs.append(HumanMessage(content=user_prompt))
        return msgs

    async def collect_data(
        self,
        state: AgentState,
        history: Optional[List[dict]] = None,
        summary: Optional[str] = None,
        extra_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Discover MCP tools, run tool-calling loop, and return raw results."""
        messages = state.get("messages") or []
        user_msg = extract_text(messages[-1].content) if messages else ""
        client_id = state.get("metadata", {}).get("client_id") or "unknown"

        tools, tool_map = await self._load_tools()

        if not tools:
            logger.warning("CRMAgent.collect_data: no MCP tools available")
            return {"tool_results": {}, "tools_called": [], "customer_id": client_id, "mcp_tools_count": 0}

        msgs = self._build_tool_messages(user_msg, client_id, history, summary, extra_context)
        llm_with_tools = self.llm.bind_tools(tools)

        tool_results: Dict[str, Any] = {}
        tools_called: List[str] = []

        for _ in range(settings.MCP_MAX_TOOL_ITERATIONS):
            ai = await llm_with_tools.ainvoke(msgs)
            if not getattr(ai, "tool_calls", None):
                break
            msgs.append(ai)

            async def _call(tc: dict) -> tuple:
                name = tc.get("name", "")
                call_id = tc.get("id", "") or name
                tool = tool_map.get(name)
                if tool is None:
                    return name, call_id, {"error": f"MCP tool '{name}' not available"}
                try:
                    return name, call_id, await tool.ainvoke(tc.get("args") or {})
                except Exception as e:
                    logger.warning(f"CRM MCP tool '{name}' failed: {e}")
                    return name, call_id, {"error": str(e)}

            results = await asyncio.gather(*[_call(tc) for tc in ai.tool_calls])
            for name, call_id, result in results:
                tool_results[name] = result
                if name not in tools_called:
                    tools_called.append(name)
                msgs.append(ToolMessage(content=str(result), tool_call_id=call_id))

        logger.info("CRMAgent.collect_data complete", extra={"customer_id": client_id, "tools_called": tools_called})
        return {"tool_results": tool_results, "tools_called": tools_called, "customer_id": client_id, "mcp_tools_count": len(tools)}

    async def run(self, state: AgentState) -> dict:
        """LangGraph node: collect CRM tool data -> store in state["crm_output"]."""
        logger.info("Running Relationship Intelligence Agent (data collection)")
        try:
            data = await self.collect_data(state)
            return {"crm_output": data}
        except Exception as e:
            logger.error(f"RelationshipIntelligenceAgent.run error: {e}", exc_info=True)
            return {"crm_output": {"tool_results": {}, "tools_called": [], "error": str(e)}}


# Module-level singleton shared across the orchestrator and graph.
relationship_intelligence_agent = RelationshipIntelligenceAgent()
