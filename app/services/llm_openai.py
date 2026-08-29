"""OpenAI LLM factory -- uses langchain_openai.ChatOpenAI directly.

Proxy note
----------
OpenAI via langchain-openai uses httpx. We inject a pre-configured
httpx.AsyncClient from llm_base.build_httpx_client() so proxy and SSL
are controlled in one place.

Also works for Azure OpenAI -- set OPENAI_BASE_URL to the Azure endpoint.

Install:  pip install langchain-openai httpx
"""
from __future__ import annotations

from typing import Optional

from app.config import settings
from app.services.llm_base import build_httpx_client
from app.utils.logger import logger


def create_openai_llm(model: str, bound_tools: Optional[list] = None):
    """Return a ChatOpenAI instance for *model* with proxy-aware httpx transport.

    Args:
        model:       OpenAI model name, e.g. ``"gpt-4o"``.
        bound_tools: Optional LangChain tools to bind.

    Returns:
        ChatOpenAI (or a tool-bound variant of it).
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise ImportError(
            "langchain-openai is not installed. Run: pip install langchain-openai"
        ) from exc

    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is not set -- required for OpenAI.")

    kwargs: dict = {
        "model": model,
        "api_key": settings.OPENAI_API_KEY,
        "temperature": settings.OPENAI_TEMPERATURE,
        "max_tokens": settings.OPENAI_MAX_TOKENS,
        "http_async_client": build_httpx_client(),  # proxy + SSL from llm_base
    }
    if settings.OPENAI_BASE_URL:
        kwargs["base_url"] = settings.OPENAI_BASE_URL

    llm = ChatOpenAI(**kwargs)
    logger.info(f"OpenAI: created ChatOpenAI model={model}")
    return llm.bind_tools(bound_tools) if bound_tools else llm
