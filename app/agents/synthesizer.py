"""Synthesizer agent.

Takes raw tool results from portfolio_output and/or crm_output, checks data
sufficiency (rule-based — no extra LLM call), then either:
  - Generates the final RM brief via one LLM call, OR
  - Asks the user for clarification when critical data is missing.

Graph node  : run(state)
Stream path : stream_run(state, history, summary)
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, extract_text
from app.agents.state import AgentState
from app.constants import (
    MAX_RETRIES,
    ROUTE_BOTH,
    ROUTE_CRM_ONLY,
    ROUTE_GENERAL,
    ROUTE_GREETING,
    ROUTE_PORTFOLIO_ONLY,
)
from app.prompts.synthesizer import (
    SYNTHESIZER_CLARIFICATION_TEMPLATE,
    SYNTHESIZER_SYSTEM_PROMPT,
    SYNTHESIZER_USER_TEMPLATE,
)
from app.utils.logger import logger


class SynthesizerAgent(BaseAgent):
    """Merges retrieved data and generates the final RM response."""

    # ── Sufficiency check (rule-based, no LLM) ────────────────────────────────

    def _check_sufficiency(self, state: AgentState) -> tuple[bool, str]:
        """Return (is_sufficient, missing_description).

        Checks whether the agents that *should* have run actually returned data.
        Rule-based: empty tool_results → not sufficient.
        """
        route = state.get("route", "general")

        if route in (ROUTE_GENERAL, ROUTE_GREETING):
            return True, ""

        portfolio_output = state.get("portfolio_output") or {}
        crm_output = state.get("crm_output") or {}
        portfolio_has_data = bool(portfolio_output.get("tool_results"))
        crm_has_data = bool(crm_output.get("tool_results"))

        needs_portfolio = route in (ROUTE_PORTFOLIO_ONLY, ROUTE_BOTH)
        needs_crm = route in (ROUTE_CRM_ONLY, ROUTE_BOTH)

        missing: list[str] = []
        if needs_portfolio and not portfolio_has_data:
            missing.append("portfolio data")
        if needs_crm and not crm_has_data:
            missing.append("CRM / interaction data")

        if missing:
            return False, " and ".join(missing)
        return True, ""

    # ── Context builder ───────────────────────────────────────────────────────

    def _build_context(self, state: AgentState) -> tuple[str, list[dict]]:
        """Format retrieved tool results into a labelled context string + citations list."""
        parts: list[str] = []
        citations: list[dict] = []

        portfolio_output = state.get("portfolio_output") or {}
        for tool_name, result in (portfolio_output.get("tool_results") or {}).items():
            # Clear source label so LLM knows to cite as [Portfolio]
            parts.append(f"--- SOURCE: Portfolio ({tool_name}) ---\n{result}")
            citations.append({"source": "portfolio", "tool": tool_name})

        crm_output = state.get("crm_output") or {}
        for tool_name, result in (crm_output.get("tool_results") or {}).items():
            # Clear source label so LLM knows to cite as [CRM]
            parts.append(f"--- SOURCE: CRM ({tool_name}) ---\n{result}")
            citations.append({"source": "crm", "tool": tool_name})

        return "\n\n".join(parts) if parts else "(no data retrieved)", citations

    # ── Internal LLM helpers ─────────────────────────────────────────────────

    def _clarification_messages(self, user_msg: str, missing: str) -> list:
        return [
            SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
            HumanMessage(content=SYNTHESIZER_CLARIFICATION_TEMPLATE.format(
                query=user_msg,
                missing_data=missing,
            )),
        ]

    def _synthesis_messages(
        self, user_msg: str, client_id: str, context: str
    ) -> list:
        return [
            SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT),
            HumanMessage(content=SYNTHESIZER_USER_TEMPLATE.format(
                query=user_msg,
                client_id=client_id,
                context=context,
            )),
        ]

    # ── Graph node ────────────────────────────────────────────────────────────

    async def run(self, state: AgentState) -> dict:
        """LangGraph node: generate final_output or clarification_needed."""
        messages = state.get("messages") or []
        user_msg = extract_text(messages[-1].content) if messages else ""
        client_id = state.get("metadata", {}).get("client_id") or "unknown"
        retry_count = state.get("retry_count") or 0

        is_sufficient, missing = self._check_sufficiency(state)

        if not is_sufficient:
            logger.info(f"Synthesizer: data insufficient ({missing}), generating clarification")
            clarification = await self.llm.ainvoke(
                self._clarification_messages(user_msg, missing)
            )
            clarification_text = extract_text(clarification.content)
            return {
                "is_sufficient": False,
                "clarification_needed": clarification_text,
                "final_output": clarification_text,
                "retry_count": retry_count,
            }

        context, citations = self._build_context(state)
        logger.info(f"Synthesizer: generating response, citations={len(citations)}")

        result = await self.llm.ainvoke(
            self._synthesis_messages(user_msg, client_id, context)
        )
        response = extract_text(result.content)
        return {
            "is_sufficient": True,
            "final_output": response,
            "citations": citations,
            "next_agent": "synthesizer",
        }

    # ── Streaming path ────────────────────────────────────────────────────────

    async def stream_run(
        self,
        state: AgentState,
        history: Optional[List[dict]] = None,
        summary: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream the synthesized response token-by-token."""
        messages = state.get("messages") or []
        user_msg = extract_text(messages[-1].content) if messages else ""
        client_id = state.get("metadata", {}).get("client_id") or "unknown"

        is_sufficient, missing = self._check_sufficiency(state)

        if not is_sufficient:
            msgs = self._clarification_messages(user_msg, missing)
        else:
            context, _ = self._build_context(state)
            msgs = self._synthesis_messages(user_msg, client_id, context)

        async for chunk in self.llm.astream(msgs):
            token = extract_text(chunk.content)
            if token:
                yield token


# Module-level singleton.
synthesizer_agent = SynthesizerAgent()
