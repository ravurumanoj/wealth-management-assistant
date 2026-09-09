"""Router / intent-classification agent.

All intent classification goes through the LLM -- no regex or hardcoded rules.
The LLM decides whether a message is a greeting, an out-of-scope request, a
portfolio query, a CRM query, both, or a general wealth question.

For the "both" route it additionally plans the execution mode (parallel vs
sequential) and, when sequential, which sub-agent produces first.

Entry points:
    * decide()             -- history-aware classifier for the streaming path;
                              returns a RouteDecision plus an updated summary.
    * classify_and_route() -- LangGraph node that sets state["route"] and the
                              execution plan.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, HISTORY_SUMMARY_THRESHOLD, extract_text
from app.agents.state import AgentState
from app.prompts.router import (
    EXECUTION_PLANNER_SYSTEM_PROMPT,
    EXECUTION_PLANNER_USER_TEMPLATE,
    ROUTER_SYSTEM_PROMPT,
    ROUTER_USER_TEMPLATE,
)
from app.constants import (
    EXEC_MODE_PARALLEL,
    EXEC_MODE_SEQUENTIAL,
    ROUTE_BOTH,
    ROUTE_CRM_ONLY,
    ROUTE_GENERAL,
    ROUTE_GREETING,
    ROUTE_OUT_OF_SCOPE,
    ROUTE_PORTFOLIO_ONLY,
    VALID_AGENTS,
    VALID_EXEC_MODES,
    VALID_ROUTES,
)
from app.utils.logger import logger


@dataclass
class RouteDecision:
    """Outcome of routing: the route plus (for 'both') the execution plan."""

    route: str
    execution_mode: Optional[str] = None  # parallel | sequential (only for 'both')
    producer: Optional[str] = None        # portfolio | crm (only when sequential)


class RouterAgent(BaseAgent):
    """LLM-based intent classifier -- all routing decisions made by the model."""

    async def classify_and_route(self, state: AgentState) -> dict:
        """LangGraph node: classify intent and set route + execution plan."""
        messages = state.get("messages") or []
        user_msg = extract_text(messages[-1].content) if messages else ""

        if not user_msg.strip():
            return {"route": ROUTE_GREETING, "execution_mode": "", "producer": ""}

        decision = await self._decide(user_msg, history_block="")
        logger.info(f"Router graph node -> {decision}")
        return {
            "route": decision.route,
            "execution_mode": decision.execution_mode or "",
            "producer": decision.producer or "",
        }

    async def decide(
        self,
        user_msg: str,
        history: Optional[list] = None,
        existing_summary: Optional[str] = None,
    ) -> tuple[RouteDecision, Optional[str]]:
        """History-aware classifier for the streaming path.

        Returns (RouteDecision, updated_summary).
        """
        logger.info("Router.decide: classifying via LLM")

        if not user_msg.strip():
            return RouteDecision(route=ROUTE_GREETING), existing_summary

        summary = existing_summary
        if len(history or []) > HISTORY_SUMMARY_THRESHOLD:
            summary = self._summarize_history(history, existing_summary)

        history_block = self._format_history_block(history or [])
        decision = await self._decide(user_msg, history_block=history_block)
        logger.info(f"Router.decide -> {decision}")
        return decision, summary

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _decide(self, user_msg: str, history_block: str = "") -> RouteDecision:
        """Classify the route and, for 'both', plan the execution mode."""
        route = await self._llm_classify(user_msg, history_block=history_block)
        if route != ROUTE_BOTH:
            return RouteDecision(route=route)

        execution_mode, producer = await self._plan_execution(user_msg, history_block)
        return RouteDecision(route=route, execution_mode=execution_mode, producer=producer)

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

            if candidate in VALID_ROUTES:
                return candidate

            # Fuzzy fallbacks when LLM output does not match exactly
            if "greet" in raw or "hello" in raw:
                return ROUTE_GREETING
            if "out" in raw and "scope" in raw:
                return ROUTE_OUT_OF_SCOPE
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

    async def _plan_execution(
        self, user_msg: str, history_block: str = ""
    ) -> tuple[str, Optional[str]]:
        """Decide parallel vs sequential for a 'both' query. Defaults to parallel."""
        msgs = [
            SystemMessage(content=EXECUTION_PLANNER_SYSTEM_PROMPT),
            HumanMessage(content=EXECUTION_PLANNER_USER_TEMPLATE.format(
                history_block=history_block,
                user_message=user_msg,
            )),
        ]
        try:
            result = await self.llm.ainvoke(msgs)
            data = self._parse_json_object(extract_text(result.content))
            mode = str(data.get("execution_mode", "")).strip().lower()
            producer = data.get("producer")
            producer = str(producer).strip().lower() if producer else None

            if mode not in VALID_EXEC_MODES:
                return EXEC_MODE_PARALLEL, None
            if mode == EXEC_MODE_SEQUENTIAL:
                if producer not in VALID_AGENTS:
                    # Sequential without a valid producer is meaningless — fall back.
                    return EXEC_MODE_PARALLEL, None
                return EXEC_MODE_SEQUENTIAL, producer
            return EXEC_MODE_PARALLEL, None
        except Exception as e:
            logger.warning(f"_plan_execution: falling back to parallel ({e})")
            return EXEC_MODE_PARALLEL, None

    @staticmethod
    def _parse_json_object(text: str) -> dict:
        """Extract the first JSON object from an LLM response; {} on failure."""
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception:
                    return {}
            return {}


# Module-level singleton shared across the orchestrator and graph.
router_agent = RouterAgent()
