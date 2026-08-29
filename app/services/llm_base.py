"""Shared utilities for all LLM provider services.

Every provider module imports from here — nothing is duplicated:
  - configure_proxy_env   set HTTP/HTTPS proxy env vars once at startup
  - get_ssl_verify        unified SSL verify value (bool | cert-path string)
  - build_httpx_client    pre-configured httpx.AsyncClient (used by OpenAI)
  - detect_provider       model-name → provider-id routing
  - invoke_with_retry     exponential-backoff retry for async callables
  - BaseLLMService        minimal protocol for the UniqueAI custom wrapper
"""
from __future__ import annotations

import asyncio
import inspect
import os
from typing import Any, AsyncIterator, Callable, List

import httpx
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

from app.config import settings
from app.utils.logger import logger


# ── Proxy helpers ─────────────────────────────────────────────────────────────

def configure_proxy_env() -> None:
    """Inject proxy settings from config into the process environment.

    Idempotent: uses os.environ.setdefault so explicit shell vars take precedence.
    Call once from get_llm() before any service is built.
    """
    if settings.HTTP_PROXY:
        os.environ.setdefault("HTTP_PROXY", settings.HTTP_PROXY)
        os.environ.setdefault("http_proxy", settings.HTTP_PROXY)
    if settings.HTTPS_PROXY:
        os.environ.setdefault("HTTPS_PROXY", settings.HTTPS_PROXY)
        os.environ.setdefault("https_proxy", settings.HTTPS_PROXY)


# ── SSL helpers ───────────────────────────────────────────────────────────────

def get_ssl_verify() -> bool | str:
    """Return the SSL verification setting understood by httpx and requests.

    Priority:  SSL_CA_CERT_PATH  >  SSL_VERIFY  >  True (default)

    Returns:
        str   — path to a CA-bundle (corporate proxy with SSL inspection)
        True  — standard certificate verification
        False — disabled (dev / SSL-intercepting proxy without a CA bundle)
    """
    if settings.SSL_CA_CERT_PATH:
        return settings.SSL_CA_CERT_PATH
    return settings.SSL_VERIFY


def apply_ssl_env(ssl: bool | str) -> None:
    """Push SSL settings into env vars picked up by requests/urllib/Google SDK."""
    if isinstance(ssl, str):
        os.environ["REQUESTS_CA_BUNDLE"] = ssl
        os.environ["SSL_CERT_FILE"] = ssl
    elif not ssl:
        os.environ["PYTHONHTTPSVERIFY"] = "0"
        logger.warning("SSL verification DISABLED globally — not safe for production")


def build_httpx_client() -> httpx.AsyncClient:
    """Build an httpx AsyncClient with proxy and SSL settings from config.

    Used by the OpenAI provider so its transport is fully controlled here.
    Handles the httpx API change: ``proxies=`` (removed in 0.28) vs ``proxy=``.
    """
    ssl = get_ssl_verify()
    proxy_url = settings.HTTPS_PROXY or settings.HTTP_PROXY

    client_kwargs: dict = {"verify": ssl}
    if proxy_url:
        params = inspect.signature(httpx.AsyncClient.__init__).parameters
        if "proxy" in params:        # httpx >= 0.26 (only option on 0.28+)
            client_kwargs["proxy"] = proxy_url
        elif "proxies" in params:     # legacy httpx < 0.28
            client_kwargs["proxies"] = proxy_url
    return httpx.AsyncClient(**client_kwargs)


# ── Model → provider detection ────────────────────────────────────────────────

def detect_provider(model_name: str) -> str:
    """Resolve *model_name* to a provider identifier string.

    Checks MODEL_TO_PROVIDER registry first, then falls back to prefix rules
    so models not explicitly listed still route correctly.
    """
    from app.constants import (
        LLM_PROVIDER_GEMINI,
        LLM_PROVIDER_OPENAI,
        LLM_PROVIDER_UNIQUE,
        MODEL_TO_PROVIDER,
    )
    if model_name in MODEL_TO_PROVIDER:
        return MODEL_TO_PROVIDER[model_name]

    m = model_name.lower()
    if m.startswith("gemini"):
        return LLM_PROVIDER_GEMINI
    if m.startswith(("gpt-", "o1-", "o3-", "o4-", "text-")):
        return LLM_PROVIDER_OPENAI
    # Custom / unknown model name — default to Unique AI
    return LLM_PROVIDER_UNIQUE


# ── Retry utility ─────────────────────────────────────────────────────────────

async def invoke_with_retry(
    coro_fn: Callable,
    *,
    max_retries: int,
    base_delay: float,
    backoff_multiplier: float,
    max_delay: float,
    provider_name: str,
) -> Any:
    """Run *coro_fn()* with exponential-backoff retry on any exception.

    Retry schedule (base=1s, multiplier=2):
      attempt 1 → wait 1 s
      attempt 2 → wait 2 s
      attempt 3 → wait 4 s  … capped at max_delay
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            delay = min(base_delay * (backoff_multiplier ** attempt), max_delay)
            logger.warning(
                f"{provider_name}: attempt {attempt + 1}/{max_retries + 1} failed "
                f"({type(exc).__name__}: {exc}). Retrying in {delay:.1f}s…"
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


# ── Base class (only needed for UniqueAI — native LangChain models don't use it) ──

class BaseLLMService:
    """Minimal LangChain-compatible interface for custom (non-LangChain) providers."""

    PROVIDER_NAME: str = "base"
    # Set True when the service runs its own retry loop, so the router does not
    # wrap it a second time (prevents nested retry multiplication).
    HANDLES_OWN_RETRY: bool = False

    async def ainvoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        raise NotImplementedError

    async def astream(
        self, messages: List[BaseMessage], **kwargs
    ) -> AsyncIterator[AIMessageChunk]:
        raise NotImplementedError
        yield  # pragma: no cover

    def bind_tools(self, tools: list, **kwargs) -> "BaseLLMService":
        raise NotImplementedError

