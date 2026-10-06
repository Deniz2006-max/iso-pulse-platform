"""Live LLM factory: OpenAI ChatOpenAI (default gpt-4o-mini)."""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from config.settings import settings

OPENAI_KEY_HINT = (
    "OPENAI_API_KEY is not set. Add it to your .env file "
    "(copy .env.example and fill OPENAI_API_KEY=sk-...) to run live "
    "LLM synthesis with ChatOpenAI."
)


class MissingOpenAIKeyError(RuntimeError):
    """Raised when live mode is requested without an API key."""


def openai_key_configured(api_key: str | None = None) -> bool:
    key = settings.openai_api_key if api_key is None else api_key
    return bool((key or "").strip())


def require_openai_api_key(api_key: str | None = None) -> str:
    """Return the API key or raise a presentation-friendly error."""
    key = (settings.openai_api_key if api_key is None else api_key) or ""
    key = key.strip()
    if not key:
        raise MissingOpenAIKeyError(OPENAI_KEY_HINT)
    return key


def llm_runtime_label(*, mock: bool | None = None) -> str:
    if mock if mock is not None else settings.use_mock_llm:
        return "mock (fast)"
    return f"ChatOpenAI · {settings.model_name}"


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """Return gpt-4o-mini (or configured OpenAI model). Mock mode never calls this."""
    api_key = require_openai_api_key()
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.model_name,
        api_key=api_key,
        temperature=settings.temperature,
    )
