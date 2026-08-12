"""Portfolio Insights agent.

Runs LLM-driven tool calling over the 4 portfolio tools and returns the raw
tool results. Final response generation is handled by SynthesizerAgent.

Graph entry point : run(state)          → stores results in state["portfolio_output"]
Streaming helper  : collect_data(state) → returns the raw data dict directly
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.agents.base import BaseAgent, extract_text
from app.agents.memory import long_term_memory  # noqa: F401  # LTM_DISABLED
from app.agents.state import AgentState
from app.config import settings
from app.prompts.portfolio_insights import (
    PORTFOLIO_INSIGHTS_SYSTEM_PROMPT,
    PORTFOLIO_INSIGHTS_USER_TEMPLATE,
    PORTFOLIO_TOOL_COLLECTION_SUFFIX,
)
from app.services.portfolio_api_tools import PORTFOLIO_TOOLS
from app.utils.logger import logger

_TOOL_MAP = {t.name: t for t in PORTFOLIO_TOOLS}


class PortfolioInsightsAgent(BaseAgent):
    """Portfolio data collector — fetches tool results, no LLM generation."""

    def _build_tool_messages(
        self,
        user_msg: str,
        client_id: str,
        history: Optional[List[dict]] = None,
        summary: Optional[str] = None,
    ) -> List[BaseMessage]:
        """Build the initial message list that primes the LLM to call tools."""
        user_prompt = PORTFOLIO_INSIGHTS_USER_TEMPLATE.format(
            user_message=user_msg + PORTFOLIO_TOOL_COLLECTION_SUFFIX,
            additional_context=f"Client ID: {client_id}",
        )
        history_msgs = self._format_history(history or [], summary=summary)
        msgs: List[BaseMessage] = [SystemMessage(content=PORTFOLIO_INSIGHTS_SYSTEM_PROMPT)]
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
    ) -> Dict[str, Any]:
        """Run the portfolio tool-calling loop and return raw results.

        Returns a dict with:
          tool_results  — {tool_name: result_dict}
          tools_called  — ordered list of tool names actually invoked
          customer_id   — resolved client ID
        """
        messages = state.get("messages") or []
        user_msg = extract_text(messages[-1].content) if messages else ""
        client_id = state.get("metadata", {}).get("client_id") or "unknown"

        msgs = self._build_tool_messages(user_msg, client_id, history, summary)
        llm_with_tools = self.llm.bind_tools(PORTFOLIO_TOOLS)

        tool_results: Dict[str, Any] = {}
        tools_called: List[str] = []

        for _ in range(settings.MCP_MAX_TOOL_ITERATIONS):
            ai = await llm_with_tools.ainvoke(msgs)
            if not getattr(ai, "tool_calls", None):
                break  # LLM produced no more tool calls
            msgs.append(ai)

            # Execute all tool calls in this round in parallel
            async def _call(tc: dict) -> tuple[str, str, Any]:
                name = tc.get("name", "")
                call_id = tc.get("id", "") or name
                tool = _TOOL_MAP.get(name)
                if tool is None:
                    return name, call_id, {"error": f"Tool '{name}' not found"}
                try:
                    return name, call_id, await tool.ainvoke(tc.get("args") or {})
                except Exception as e:
                    logger.warning(f"Portfolio tool '{name}' failed: {e}")
                    return name, call_id, {"error": str(e)}

            results = await asyncio.gather(*[_call(tc) for tc in ai.tool_calls])
            for name, call_id, result in results:
                tool_results[name] = result
                if name not in tools_called:
                    tools_called.append(name)
                msgs.append(ToolMessage(content=str(result), tool_call_id=call_id))

        logger.info(
            "PortfolioAgent.collect_data complete",
            extra={"customer_id": client_id, "tools_called": tools_called},
        )
        return {
            "tool_results": tool_results,
            "tools_called": tools_called,
            "customer_id": client_id,
        }

    async def run(self, state: AgentState) -> dict:
        """LangGraph node: collect portfolio tool data → store in state['portfolio_output']."""
        logger.info("Running Portfolio Insights Agent (data collection)")
        try:
            data = await self.collect_data(state)
            return {"portfolio_output": data}
        except Exception as e:
            logger.error(f"PortfolioInsightsAgent.run error: {e}", exc_info=True)
            return {"portfolio_output": {"tool_results": {}, "tools_called": [], "error": str(e)}}


# Module-level singleton shared across the orchestrator and graph.
portfolio_insights_agent = PortfolioInsightsAgent()
