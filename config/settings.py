from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


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
    database_url: str


def load_settings() -> Settings:
    return Settings(
        use_mock_llm=_as_bool(os.getenv("ISO_PULSE_USE_MOCK_LLM"), True),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        model_name=os.getenv("ISO_PULSE_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("ISO_PULSE_TEMPERATURE", "0")),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://iso_pulse:iso_pulse@localhost:5432/iso_pulse",
        ),
    )


settings = load_settings()
