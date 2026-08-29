"""Router / intent-classification agent.

All intent classification goes through the LLM -- no regex or hardcoded rules.
The LLM decides whether a message is a greeting, portfolio query, CRM query, or both.

Two entry points:
    * classify_intent()    -- history-aware classifier for the streaming path.
    * classify_and_route() -- LangGraph graph node that sets state["route"].
"""
from __future__ import annotations

from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, HISTORY_SUMMARY_THRESHOLD, extract_text
from app.agents.state import AgentState
from app.prompts.router import ROUTER_SYSTEM_PROMPT, ROUTER_USER_TEMPLATE
from app.constants import (
    ROUTE_BOTH,
    ROUTE_CRM_ONLY,
    ROUTE_GENERAL,
    ROUTE_PORTFOLIO_ONLY,
    VALID_ROUTES,
)
from app.utils.logger import logger

# Valid LLM-emitted route labels
_ROUTES = VALID_ROUTES


class RouterAgent(BaseAgent):
    """LLM-based intent classifier -- all routing decisions made by the model."""

    async def classify_and_route(self, state: AgentState) -> dict:
        """LangGraph node: LLM classifies intent and sets state["route"]."""
        messages = state.get("messages") or []
        user_msg = extract_text(messages[-1].content) if messages else ""

        if not user_msg.strip():
            return {"route": ROUTE_GENERAL}

        route = await self._llm_classify(user_msg, history_block="")
        logger.info(f"Router graph node -> {route}")
        return {"route": route}

    async def classify_intent(
        self,
        user_msg: str,
        history: Optional[list] = None,
        existing_summary: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """History-aware LLM classifier for the streaming path.

        Returns (route, updated_summary).
        Route is one of: portfolio_only | crm_only | both | general.
        """
        logger.info("classify_intent: classifying via LLM")

        if not user_msg.strip():
            return ROUTE_GENERAL, existing_summary

        summary = existing_summary
        if len(history or []) > HISTORY_SUMMARY_THRESHOLD:
            summary = self._summarize_history(history, existing_summary)

        history_block = self._format_history_block(history or [])
        route = await self._llm_classify(user_msg, history_block=history_block)
        logger.info(f"classify_intent -> {route}")
        return route, summary

    async def _llm_classify(self, user_msg: str, history_block: str = "") -> str:
        """Call the LLM and map its output to a valid route label."""
        msgs = [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(content=ROUTER_USER_TEMPLATE.format(
                history_block=history_block,
                user_message=user_msg,
            )),
        ]
        try:
            result = await self.llm.ainvoke(msgs)
            raw = extract_text(result.content).strip().lower().rstrip(".")
            candidate = raw.split()[0] if raw.split() else ""

            if candidate in _ROUTES:
                return candidate

            # Fuzzy fallbacks when LLM output does not match exactly
            if "crm" in raw or "interaction" in raw or "relationship" in raw:
                return ROUTE_CRM_ONLY
            if "portfolio" in raw or "invest" in raw or "holding" in raw:
                return ROUTE_PORTFOLIO_ONLY
            if "both" in raw:
                return ROUTE_BOTH

            logger.warning(f"_llm_classify: unrecognised '{raw}', defaulting to general")
            return ROUTE_GENERAL

        except Exception as e:
            logger.error(f"_llm_classify error: {e}", exc_info=True)
            return ROUTE_GENERAL


# Module-level singleton shared across the orchestrator and graph.
router_agent = RouterAgent()
