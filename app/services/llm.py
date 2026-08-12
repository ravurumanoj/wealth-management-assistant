# GEMINI_DISABLED — Unique AI is active on this machine.
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_openai import ChatOpenAI  # NOT used — Unique SDK has its own auth format

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, List, Optional

import unique_sdk
from langchain_core.messages import (
    AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult

from app.config import settings
from app.utils.logger import logger


# ── Minimal LangChain-compatible wrapper around unique_sdk ────────────────────

class _UniqueAILLM:
    """Duck-typed LangChain chat model backed by unique_sdk.ChatCompletion.create_async.

    Exposes only the three methods our agents use: ainvoke, astream, bind_tools.
    No inheritance needed — agents call these by name, not by type.
    """

    def __init__(self, bound_tools: Optional[list] = None) -> None:
        self._bound_tools = bound_tools or []
        # Configure SDK once at creation time
        unique_sdk.api_key = settings.UNIQUE_APP_KEY
        unique_sdk.app_id = settings.UNIQUE_APP_ID
        if settings.UNIQUE_API_BASE_URL:
            unique_sdk.api_base = settings.UNIQUE_API_BASE_URL
        # Use corporate CA cert bundle if provided; otherwise default SSL verification
        if settings.SSL_CA_CERT_PATH:
            unique_sdk.api_verify_mode = settings.SSL_CA_CERT_PATH
            logger.info(f"Unique AI: using CA cert: {settings.SSL_CA_CERT_PATH}")
        else:
            unique_sdk.api_verify_mode = True

    # ── message conversion ────────────────────────────────────────────────────

    @staticmethod
    def _to_sdk_messages(messages: List[BaseMessage]) -> list:
        result = []
        for m in messages:
            if isinstance(m, SystemMessage):
                result.append({"role": "system", "content": str(m.content or "")})
            elif isinstance(m, HumanMessage):
                result.append({"role": "user", "content": str(m.content or "")})
            elif isinstance(m, AIMessage):
                msg: dict = {"role": "assistant", "content": str(m.content or "")}
                if getattr(m, "tool_calls", None):
                    msg["tool_calls"] = m.tool_calls
                result.append(msg)
            elif isinstance(m, ToolMessage):
                result.append({
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "content": str(m.content or ""),
                })
            else:
                result.append({"role": "user", "content": str(m.content or "")})
        return result

    @staticmethod
    def _extract_content(result: Any) -> str:
        choices = getattr(result, "choices", None) or result.get("choices", []) if isinstance(result, dict) else []
        if not choices:
            return ""
        first = choices[0]
        msg = first.get("message", {}) if isinstance(first, dict) else getattr(first, "message", {})
        if isinstance(msg, dict):
            return str(msg.get("content") or "")
        return str(getattr(msg, "content", "") or "")

    # ── tools → SDK options format ────────────────────────────────────────────

    @staticmethod
    def _tools_to_options(tools: list) -> dict:
        """Convert LangChain tool schemas to unique_sdk options format."""
        sdk_tools = []
        for t in tools:
            schema = getattr(t, "args_schema", None)
            params = schema.schema() if schema else {"type": "object", "properties": {}}
            sdk_tools.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": params,
                },
            })
        return {"tools": sdk_tools} if sdk_tools else {}

    # ── public LangChain-compatible API ──────────────────────────────────────

    async def ainvoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        sdk_msgs = self._to_sdk_messages(messages)
        params: dict = {
            "model": settings.UNIQUE_MODEL_NAME,
            "messages": sdk_msgs,
        }
        if self._bound_tools:
            params["options"] = self._tools_to_options(self._bound_tools)

        result = await unique_sdk.ChatCompletion.create_async(
            company_id=settings.UNIQUE_COMPANY_ID,
            user_id=settings.UNIQUE_USER_ID or None,
            **params,
        )
        content = self._extract_content(result)
        logger.debug(f"Unique AI ainvoke: {len(content)} chars")
        return AIMessage(content=content)

    async def astream(self, messages: List[BaseMessage], **kwargs) -> AsyncIterator[AIMessageChunk]:
        # unique_sdk has no streaming API; generate full response and yield once
        ai_msg = await self.ainvoke(messages, **kwargs)
        yield AIMessageChunk(content=ai_msg.content)

    def bind_tools(self, tools: list, **kwargs) -> "_UniqueAILLM":
        clone = _UniqueAILLM(bound_tools=list(tools))
        return clone


# ── Public factory used by BaseAgent ─────────────────────────────────────────

def get_llm() -> _UniqueAILLM:
    """Return the active LLM instance (Unique AI via unique_sdk)."""
    # GEMINI_DISABLED — uncomment the block below and delete the _UniqueAILLM
    # return to switch back to Gemini:
    # if not settings.GOOGLE_API_KEY:
    #     raise ValueError("GOOGLE_API_KEY is not configured.")
    # from langchain_google_genai import ChatGoogleGenerativeAI
    # return ChatGoogleGenerativeAI(
    #     model=settings.GEMINI_MODEL,
    #     google_api_key=settings.GOOGLE_API_KEY,
    #     temperature=settings.GEMINI_TEMPERATURE,
    #     max_tokens=settings.GEMINI_MAX_TOKENS,
    #     convert_system_message_to_human=True,
    # )

    if not settings.UNIQUE_APP_KEY:
        raise ValueError("UNIQUE_APP_KEY is not configured. Set it in .env.")
    logger.info(f"Initialized Unique AI LLM: {settings.UNIQUE_MODEL_NAME}")
    return _UniqueAILLM()

