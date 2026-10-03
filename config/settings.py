from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.example")


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    use_mock_llm: bool
    openai_api_key: str
    model_name: str
    temperature: float
    ollama_base_url: str
    chroma_persist_dir: Path
    chroma_collection: str
    embedding_model: str
    daily_updates_dir: Path
    reports_dir: Path


def load_settings() -> Settings:
    model_name = os.getenv("MODEL_NAME") or os.getenv("ISO_PULSE_MODEL", "qwen2.5:7b")
    return Settings(
        use_mock_llm=_as_bool(os.getenv("ISO_PULSE_USE_MOCK_LLM"), True),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        model_name=model_name,
        temperature=float(os.getenv("ISO_PULSE_TEMPERATURE", "0")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
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
    )


settings = load_settings()
