from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.example")

LOGGER = logging.getLogger("iso_pulse.settings")


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_chat_model() -> str:
    """Prefer OpenAI model ids; ignore leftover Ollama tags such as qwen2.5:7b."""
    raw = (
        os.getenv("OPENAI_MODEL")
        or os.getenv("ISO_PULSE_MODEL")
        or os.getenv("MODEL_NAME")
        or "gpt-4o-mini"
    ).strip()
    lowered = raw.lower()
    if not raw or ":" in raw or "qwen" in lowered or lowered.startswith("llama"):
        if raw and raw != "gpt-4o-mini":
            LOGGER.warning("Ignoring non-OpenAI model %r; using gpt-4o-mini", raw)
        return "gpt-4o-mini"
    return raw


@dataclass(frozen=True)
class Settings:
    use_mock_llm: bool
    openai_api_key: str
    model_name: str
    temperature: float
    chroma_persist_dir: Path
    chroma_collection: str
    embedding_model: str
    daily_updates_dir: Path
    reports_dir: Path
    daily_cache_path: Path


def load_settings() -> Settings:
    return Settings(
        use_mock_llm=_as_bool(os.getenv("ISO_PULSE_USE_MOCK_LLM"), True),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        model_name=_resolve_chat_model(),
        temperature=float(os.getenv("ISO_PULSE_TEMPERATURE", "0")),
        chroma_persist_dir=Path(
            os.getenv("CHROMA_PERSIST_DIR", str(_ROOT / "data" / "chroma_db"))
        ),
        chroma_collection=os.getenv("CHROMA_COLLECTION", "iso_mevzuat_baseline"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
        daily_updates_dir=Path(
            os.getenv("DAILY_UPDATES_DIR", str(_ROOT / "data" / "daily_updates"))
        ),
        reports_dir=Path(
            os.getenv("REPORTS_DIR", str(_ROOT / "data" / "reports"))
        ),
        daily_cache_path=Path(
            os.getenv(
                "DAILY_CACHE_PATH",
                str(_ROOT / "data" / "daily_revisions_cache.sqlite"),
            )
        ),
    )


settings = load_settings()
