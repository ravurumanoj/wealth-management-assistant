"""Lightweight direct responders that bypass the full synthesizer.

- Greeting  -> a short natural reply streamed from the LLM (Direct Reply).
- Out of scope -> a deterministic, auditable canned message (Safe Decline).
"""
from __future__ import annotations

from typing import AsyncGenerator, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import BaseAgent, extract_text
from app.constants import SAFE_DECLINE_MESSAGE
from app.prompts.direct_reply import (
    DIRECT_REPLY_SYSTEM_PROMPT,
    DIRECT_REPLY_USER_TEMPLATE,
)


class DirectResponder(BaseAgent):
    """Greeting direct-reply (light LLM call) and out-of-scope safe-decline (constant)."""

    async def stream_greeting(
        self,
        user_msg: str,
        history: Optional[List[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream a short, natural greeting reply token-by-token."""
        history_block = self._format_history_block(history or [])
        msgs = [
            SystemMessage(content=DIRECT_REPLY_SYSTEM_PROMPT),
            HumanMessage(content=DIRECT_REPLY_USER_TEMPLATE.format(
                history_block=history_block,
                user_message=user_msg,
            )),
        ]
        async for chunk in self.llm.astream(msgs):
            token = extract_text(chunk.content)
            if token:
                yield token

    async def reply_greeting(
        self,
        user_msg: str,
        history: Optional[List[dict]] = None,
    ) -> str:
        """Return a short greeting reply in one shot (non-streaming graph path)."""
        history_block = self._format_history_block(history or [])
        msgs = [
            SystemMessage(content=DIRECT_REPLY_SYSTEM_PROMPT),
            HumanMessage(content=DIRECT_REPLY_USER_TEMPLATE.format(
                history_block=history_block,
                user_message=user_msg,
            )),
        ]
        result = await self.llm.ainvoke(msgs)
        return extract_text(result.content)

    @staticmethod
    def safe_decline() -> str:
        """Return the deterministic out-of-scope decline message."""
        return SAFE_DECLINE_MESSAGE


# Module-level singleton shared across the orchestrator and graph.
direct_responder = DirectResponder()
