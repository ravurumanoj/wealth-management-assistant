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
from app.agents.execution import evaluate_sufficiency
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
    SYNTHESIZER_PARTIAL_NOTICE,
    SYNTHESIZER_SYSTEM_PROMPT,
    SYNTHESIZER_USER_TEMPLATE,
)
from app.utils.logger import logger


class SynthesizerAgent(BaseAgent):
    """Merges retrieved data and generates the final RM response."""

    # ── Sufficiency check (rule-based, no LLM) ────────────────────────────────

    def _check_sufficiency(self, state: AgentState) -> tuple[bool, str]:
        """Return (is_sufficient, missing_description).

        Delegates to the shared ``evaluate_sufficiency`` so the streaming and
        graph paths use identical rules.
        """
        route = state.get("route", "general")

        if route in (ROUTE_GENERAL, ROUTE_GREETING):
            return True, ""

        is_sufficient, missing, _ = evaluate_sufficiency(
            route,
            state.get("portfolio_output") or {},
            state.get("crm_output") or {},
        )
        return is_sufficient, missing

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

        # Long-term episodic recall (per client), when available.
        ltm_context = (state.get("ltm_context") or "").strip()
        if ltm_context:
            parts.append(f"--- LONG-TERM MEMORY ---\n{ltm_context}")

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
        self, user_msg: str, client_id: str, context: str,
        partial_missing: Optional[str] = None,
    ) -> list:
        if partial_missing:
            context = (
                SYNTHESIZER_PARTIAL_NOTICE.format(missing_data=partial_missing)
                + "\n\n"
                + context
            )
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
        """LangGraph node: generate the final response.

        Sufficiency and the re-fetch/replan loop are handled by dedicated graph
        nodes; here we synthesize whatever data is available and, if retrieval
        stayed incomplete, add a partial-answer notice (FR-ORC-005).
        """
        messages = state.get("messages") or []
        user_msg = extract_text(messages[-1].content) if messages else ""
        client_id = state.get("metadata", {}).get("client_id") or "unknown"

        is_sufficient, missing = self._check_sufficiency(state)
        partial_missing = missing if not is_sufficient else None

        context, citations = self._build_context(state)
        logger.info(
            f"Synthesizer: generating response, citations={len(citations)}, "
            f"partial={bool(partial_missing)}"
        )

        result = await self.llm.ainvoke(
            self._synthesis_messages(user_msg, client_id, context, partial_missing)
        )
        response = extract_text(result.content)
        return {
            "is_sufficient": is_sufficient,
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
        partial_missing: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream the synthesized response token-by-token.

        ``partial_missing`` is set by the orchestrator when retrieval stayed
        incomplete after all re-fetch attempts, so the answer flags the gap.
        """
        messages = state.get("messages") or []
        user_msg = extract_text(messages[-1].content) if messages else ""
        client_id = state.get("metadata", {}).get("client_id") or "unknown"

        context, _ = self._build_context(state)
        msgs = self._synthesis_messages(user_msg, client_id, context, partial_missing)

        async for chunk in self.llm.astream(msgs):
            token = extract_text(chunk.content)
            if token:
                yield token


# Module-level singleton.
synthesizer_agent = SynthesizerAgent()
