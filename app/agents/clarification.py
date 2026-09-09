"""Pre-dispatch Clarification / Disambiguation gate.

Runs after routing and before the sub-agents fetch data (only for data routes).
It decides whether the RM's query is specific enough, or whether the RM must
first pick between multiple matching records or supply a missing detail.

FR-COM-002: where a query matches more than one client / portfolio / meeting,
the system must ask the RM to choose and must not choose silently.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, extract_text
from app.constants import CLARIFY_ASK, CLARIFY_PROCEED, VALID_CLARIFY_ACTIONS
from app.prompts.clarification import (
    CLARIFICATION_SYSTEM_PROMPT,
    CLARIFICATION_USER_TEMPLATE,
)
from app.services.clients import format_client_roster, load_clients
from app.utils.logger import logger


@dataclass
class ClarificationDecision:
    """Gate outcome: proceed with retrieval, or ask the RM a question first."""

    action: str                      # proceed | clarify
    question: Optional[str] = None   # set only when action == clarify

    @property
    def needs_clarification(self) -> bool:
        return self.action == CLARIFY_ASK and bool(self.question)


class ClarificationAgent(BaseAgent):
    """LLM-based disambiguation gate grounded on the known client/portfolio context."""

    async def assess(
        self,
        user_msg: str,
        client_id: str,
        active_portfolio_ids: Optional[List[str]] = None,
        history: Optional[List[dict]] = None,
        summary: Optional[str] = None,
        authorized_client_ids: Optional[set] = None,
    ) -> ClarificationDecision:
        """Decide whether to proceed or ask the RM to disambiguate.

        Fails open (proceed) on any error so a gate failure never blocks a valid query.
        When ``authorized_client_ids`` is provided, only those clients are offered
        as disambiguation options (FR-COM-002 — authorized matches only).
        """
        if not user_msg.strip():
            return ClarificationDecision(action=CLARIFY_PROCEED)

        clients = load_clients()
        if authorized_client_ids is not None:
            clients = [c for c in clients if str(c.get("id")) in authorized_client_ids]
        roster = format_client_roster(clients)
        portfolios = ", ".join(active_portfolio_ids) if active_portfolio_ids else "(none specified)"
        history_block = self._format_history_block(history or [])

        msgs = [
            SystemMessage(content=CLARIFICATION_SYSTEM_PROMPT),
            HumanMessage(content=CLARIFICATION_USER_TEMPLATE.format(
                client_id=client_id or "(none selected)",
                active_portfolios=portfolios,
                client_roster=roster,
                history_block=history_block,
                user_message=user_msg,
            )),
        ]

        try:
            result = await self.llm.ainvoke(msgs)
            data = self._parse_json_object(extract_text(result.content))
            action = str(data.get("action", "")).strip().lower()

            if action not in VALID_CLARIFY_ACTIONS:
                logger.warning(f"ClarificationAgent: unrecognised action '{action}', proceeding")
                return ClarificationDecision(action=CLARIFY_PROCEED)

            if action == CLARIFY_ASK:
                question = str(data.get("question", "")).strip()
                if not question:
                    return ClarificationDecision(action=CLARIFY_PROCEED)
                return ClarificationDecision(action=CLARIFY_ASK, question=question)

            return ClarificationDecision(action=CLARIFY_PROCEED)

        except Exception as e:
            logger.warning(f"ClarificationAgent.assess failed, proceeding ({e})")
            return ClarificationDecision(action=CLARIFY_PROCEED)

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
clarification_agent = ClarificationAgent()
