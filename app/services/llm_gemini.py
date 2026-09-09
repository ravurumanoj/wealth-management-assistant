"""Gemini LLM factory -- uses langchain_google_genai.ChatGoogleGenerativeAI directly.

Corporate proxy note
--------------------
Gemini defaults to gRPC which ignores HTTP_PROXY env vars. Setting
``transport="rest"`` switches to HTTPS/REST so the proxy env vars injected
by configure_proxy_env() (in llm_base) and SSL settings apply correctly.

Install:  pip install langchain-google-genai
"""
from __future__ import annotations

from typing import Optional

from app.config import settings
from app.services.llm_base import apply_ssl_env, get_ssl_verify
from app.utils.logger import logger


def create_gemini_llm(model: str, bound_tools: Optional[list] = None):
    """Return a ChatGoogleGenerativeAI instance for *model*.

    Proxy env vars must already be set by configure_proxy_env() before
    calling this (done once in get_llm()).

    Args:
        model:       Gemini model name, e.g. ``"gemini-1.5-pro"``.
        bound_tools: Optional LangChain tools to bind.

    Returns:
        ChatGoogleGenerativeAI (or a tool-bound variant of it).
    """
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise ImportError(
            "langchain-google-genai is not installed. "
            "Run: pip install langchain-google-genai"
        ) from exc

    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set -- required for Gemini.")

    # Apply SSL env vars so the underlying REST HTTP client respects them
    apply_ssl_env(get_ssl_verify())

    kwargs = dict(
        model=model,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=settings.GEMINI_TEMPERATURE,
        max_output_tokens=settings.GEMINI_MAX_TOKENS,
        convert_system_message_to_human=True,
    )
    # transport="rest" (proxy support) is only valid on older langchain-google-genai
    # builds; on newer ones it leaks into model_kwargs, so pass it only if accepted.
    if "transport" in getattr(ChatGoogleGenerativeAI, "model_fields", {}):
        kwargs["transport"] = "rest"  # REST honours HTTPS_PROXY; gRPC does not

    llm = ChatGoogleGenerativeAI(**kwargs)
    logger.info(f"Gemini: created ChatGoogleGenerativeAI model={model}")
    return llm.bind_tools(bound_tools) if bound_tools else llm
