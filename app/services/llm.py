# ── LLM Router ───────────────────────────────────────────────────────────────
# Invokes the configured model, and on failure walks an ordered fallback model
# chain. Primary purpose: route each call to the right provider for the chosen
# model; fallback is the safety net.
#
# Configuration via .env:
#   LLM_PROVIDER            primary provider  (unique_ai | gemini | openai)
#   LLM_FALLBACK_MODELS     ordered fallback model names, comma-separated
#                           e.g. "gemini-1.5-pro,gpt-4o,gemini-1.5-flash"
#   LLM_MAX_RETRIES / LLM_RETRY_BASE_DELAY / ...   retry tuning
#   HTTP_PROXY / HTTPS_PROXY / SSL_VERIFY / SSL_CA_CERT_PATH   network
#
# Dynamic override:
#   get_llm()                     → primary model from config
#   get_llm(model="gpt-4o")       → gpt-4o becomes primary; config fallbacks apply

from __future__ import annotations

from typing import Any, AsyncIterator, List, Optional

from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage

from app.config import settings
from app.constants import LLM_PROVIDER_GEMINI, LLM_PROVIDER_OPENAI, LLM_PROVIDER_UNIQUE
from app.services.llm_base import (
    configure_proxy_env,
    detect_provider,
    invoke_with_retry,
)
from app.utils.logger import logger


# ── Service factory ───────────────────────────────────────────────────────────

def _create_service(model: str, bound_tools: Optional[list] = None):
    """Build the appropriate LLM object for *model*.

    For Gemini / OpenAI this returns a native LangChain BaseChatModel
    (ChatGoogleGenerativeAI / ChatOpenAI) — no extra wrapper.
    For Unique AI it returns UniqueAILLM (custom wrapper, no LangChain package).
    """
    provider = detect_provider(model)

    if provider == LLM_PROVIDER_GEMINI:
        from app.services.llm_gemini import create_gemini_llm
        return create_gemini_llm(model, bound_tools)

    if provider == LLM_PROVIDER_OPENAI:
        from app.services.llm_openai import create_openai_llm
        return create_openai_llm(model, bound_tools)

    # unique_ai (or any unrecognised provider)
    from app.services.llm_unique import UniqueAILLM
    return UniqueAILLM(bound_tools=bound_tools)


def _primary_model() -> str:
    """Return the model name for the configured primary provider."""
    p = settings.LLM_PROVIDER
    if p == LLM_PROVIDER_GEMINI:
        return settings.GEMINI_MODEL
    if p == LLM_PROVIDER_OPENAI:
        return settings.OPENAI_MODEL
    return settings.UNIQUE_MODEL_NAME


# ── LLMRouter ─────────────────────────────────────────────────────────────────

class LLMRouter:
    """Routes each call to the configured model, falling back on failure.

    Model list = [primary_model, *config_fallbacks]. The primary is invoked
    first; each subsequent model is tried only if the previous one fails after
    exhausting its retries.

    Retry is applied here for native LangChain models (Gemini / OpenAI). A
    provider whose service sets ``HANDLES_OWN_RETRY = True`` (Unique AI) is
    called directly so its own retry loop is not duplicated.

    Service instances are cached per model name so httpx clients are not
    recreated on every call.
    """

    def __init__(
        self,
        models: List[str],
        bound_tools: Optional[list] = None,
    ) -> None:
        self._models = models
        self._bound_tools: list = bound_tools or []
        # Cache built lazily on first use per model
        self._cache: dict = {}

    def _svc(self, model: str):
        if model not in self._cache:
            self._cache[model] = _create_service(model, self._bound_tools or None)
        return self._cache[model]

    async def _invoke_one(self, model: str, messages: List[BaseMessage], **kwargs) -> AIMessage:
        """Invoke a single model, adding router-level retry only when needed."""
        svc = self._svc(model)
        if getattr(svc, "HANDLES_OWN_RETRY", False):
            # Provider retries internally (Unique AI) — don't double-wrap
            return await svc.ainvoke(messages, **kwargs)
        return await invoke_with_retry(
            lambda: svc.ainvoke(messages, **kwargs),
            max_retries=settings.LLM_MAX_RETRIES,
            base_delay=settings.LLM_RETRY_BASE_DELAY,
            backoff_multiplier=settings.LLM_RETRY_BACKOFF_MULTIPLIER,
            max_delay=settings.LLM_RETRY_MAX_DELAY,
            provider_name=model,
        )

    # ── ainvoke ───────────────────────────────────────────────────────────────

    async def ainvoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        """Invoke primary model; fall back through the list on failure."""
        last_exc: Exception | None = None
        for model in self._models:
            try:
                result = await self._invoke_one(model, messages, **kwargs)
                if model != self._models[0]:
                    logger.info(f"LLMRouter: used fallback model '{model}'")
                return result
            except Exception as exc:
                logger.warning(
                    f"LLMRouter: model '{model}' exhausted retries "
                    f"— {type(exc).__name__}: {exc}"
                )
                last_exc = exc
        raise last_exc or RuntimeError("All configured LLM models failed")

    # ── astream ───────────────────────────────────────────────────────────────

    async def astream(
        self, messages: List[BaseMessage], **kwargs
    ) -> AsyncIterator[AIMessageChunk]:
        """Stream from primary model; fall back only if no token was emitted yet.

        Once the first token reaches the caller we cannot restart the stream,
        so a mid-stream failure propagates immediately.
        """
        last_exc: Exception | None = None
        for model in self._models:
            tokens_yielded = False
            try:
                async for chunk in self._svc(model).astream(messages, **kwargs):
                    tokens_yielded = True
                    yield chunk
                if model != self._models[0]:
                    logger.info(f"LLMRouter: astream used fallback model '{model}'")
                return
            except Exception as exc:
                if tokens_yielded:
                    logger.error(
                        f"LLMRouter: model '{model}' failed mid-stream — cannot fall back"
                    )
                    raise
                logger.warning(
                    f"LLMRouter: model '{model}' failed before streaming "
                    f"— {type(exc).__name__}: {exc}. Trying next model…"
                )
                last_exc = exc
        raise last_exc or RuntimeError("All configured LLM models failed during streaming")

    # ── sync + structured-output helpers ──────────────────────────────────────

    def invoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        """Synchronous wrapper around ainvoke (best-effort, non-async contexts)."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            raise RuntimeError("LLMRouter.invoke() cannot be called inside a running event loop; use ainvoke().")
        return asyncio.run(self.ainvoke(messages, **kwargs))

    def with_structured_output(self, schema: Any, **kwargs):
        """Delegate structured output to the primary model's native support.

        Works for Gemini / OpenAI (native LangChain models). Unique AI has no
        structured-output API, so callers should handle the AttributeError and
        fall back to prompt-based extraction.
        """
        return self._svc(self._models[0]).with_structured_output(schema, **kwargs)

    # ── bind_tools ────────────────────────────────────────────────────────────

    def bind_tools(self, tools: list, **kwargs) -> "LLMRouter":
        """Return a new LLMRouter with *tools* bound to every provider."""
        return LLMRouter(self._models, bound_tools=list(tools))


# ── Public factory ────────────────────────────────────────────────────────────

def get_llm(model: Optional[str] = None) -> LLMRouter:
    """Return an LLMRouter configured with proxy, primary model, and fallbacks.

    Args:
        model: Optional model name to use as primary, overriding config.
               When omitted, the primary comes from LLM_PROVIDER's model setting.
               Config fallback models still apply underneath either way.
    """
    configure_proxy_env()  # set proxy env vars before any service is built

    primary = model or _primary_model()
    fallbacks = settings.LLM_FALLBACK_MODELS_LIST
    # Dedupe: primary must not appear again in the fallback chain
    models = [primary] + [m for m in fallbacks if m != primary]

    logger.info(
        f"LLM: primary={primary}"
        + (f", fallbacks={[m for m in models[1:]]}" if len(models) > 1 else ", no fallbacks")
    )
    return LLMRouter(models=models)



