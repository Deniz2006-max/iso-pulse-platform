from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from config.settings import settings


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """Return the live chat model. Mock mode never calls this."""
    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.model_name,
        base_url=settings.ollama_base_url,
        temperature=settings.temperature,
    )
