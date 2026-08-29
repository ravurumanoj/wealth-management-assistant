"""Unique AI LLM service.

There is no official LangChain package for Unique AI, so we keep a custom
wrapper here. Proxy and SSL are handled through shared utilities in llm_base.
"""
from __future__ import annotations

from typing import Any, AsyncIterator, List, Optional

import unique_sdk
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from app.config import settings
from app.constants import LLM_PROVIDER_UNIQUE
from app.services.llm_base import BaseLLMService, apply_ssl_env, get_ssl_verify, invoke_with_retry
from app.utils.logger import logger


class UniqueAILLM(BaseLLMService):
    """LangChain-compatible wrapper around unique_sdk with configurable retry."""

    PROVIDER_NAME: str = LLM_PROVIDER_UNIQUE
    # This wrapper retries internally via invoke_with_retry, so the router must
    # not add a second retry layer around it.
    HANDLES_OWN_RETRY: bool = True

    def __init__(self, bound_tools: Optional[list] = None) -> None:
        self._bound_tools: list = bound_tools or []
        self._configure_sdk()

    # ── SDK initialisation ────────────────────────────────────────────────────

    def _configure_sdk(self) -> None:
        unique_sdk.api_key = settings.UNIQUE_APP_KEY
        unique_sdk.app_id = settings.UNIQUE_APP_ID
        if settings.UNIQUE_API_BASE_URL:
            unique_sdk.api_base = settings.UNIQUE_API_BASE_URL

        ssl = get_ssl_verify()  # from llm_base — single source of truth
        if isinstance(ssl, str):
            unique_sdk.api_verify_mode = ssl
            apply_ssl_env(ssl)
            logger.info(f"Unique AI: CA cert configured: {ssl}")
        elif not ssl:
            unique_sdk.api_verify_mode = False
            logger.warning("Unique AI: SSL verification DISABLED — not safe for production")
        else:
            unique_sdk.api_verify_mode = True

    # ── Message format conversion ─────────────────────────────────────────────

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
                result.append(
                    {
                        "role": "tool",
                        "tool_call_id": m.tool_call_id,
                        "content": str(m.content or ""),
                    }
                )
            else:
                result.append({"role": "user", "content": str(m.content or "")})
        return result

    @staticmethod
    def _extract_content(result: Any) -> str:
        choices = (
            getattr(result, "choices", None)
            or (result.get("choices", []) if isinstance(result, dict) else [])
        )
        if not choices:
            return ""
        first = choices[0]
        msg = (
            first.get("message", {}) if isinstance(first, dict)
            else getattr(first, "message", {})
        )
        if isinstance(msg, dict):
            return str(msg.get("content") or "")
        return str(getattr(msg, "content", "") or "")

    @staticmethod
    def _tools_to_options(tools: list) -> dict:
        sdk_tools = []
        for t in tools:
            schema = getattr(t, "args_schema", None)
            params = schema.schema() if schema else {"type": "object", "properties": {}}
            sdk_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": params,
                    },
                }
            )
        return {"tools": sdk_tools} if sdk_tools else {}

    # ── Public LangChain-compatible API ───────────────────────────────────────

    async def ainvoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        async def _call() -> AIMessage:
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

        return await invoke_with_retry(
            _call,
            max_retries=settings.LLM_MAX_RETRIES,
            base_delay=settings.LLM_RETRY_BASE_DELAY,
            backoff_multiplier=settings.LLM_RETRY_BACKOFF_MULTIPLIER,
            max_delay=settings.LLM_RETRY_MAX_DELAY,
            provider_name=self.PROVIDER_NAME,
        )

    async def astream(
        self, messages: List[BaseMessage], **kwargs
    ) -> AsyncIterator[AIMessageChunk]:
        # unique_sdk has no streaming — fetch full response, yield as one chunk
        ai_msg = await self.ainvoke(messages, **kwargs)
        yield AIMessageChunk(content=ai_msg.content)

    def bind_tools(self, tools: list, **kwargs) -> "UniqueAILLM":
        return UniqueAILLM(bound_tools=list(tools))

