from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── PostgreSQL ──────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://isopulse:isopulse_secret@postgres:5432/iso_pulse"

    # ── ChromaDB ────────────────────────────────────────────────────────────
    chroma_host: str = "chromadb"
    chroma_port: int = 8000

    # ── Ollama ──────────────────────────────────────────────────────────────
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b"

    # ── SMTP ────────────────────────────────────────────────────────────────
    smtp_host: str = "smtp_dev"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@isopulse.local"

    # ── Uygulama ────────────────────────────────────────────────────────────
    secret_key: str = "change_me_in_production_32_chars_min"
    environment: str = "development"
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
