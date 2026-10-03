from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

SourceName = Literal["resmi_gazete", "sgk", "mevzuat"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# SGK duyuru/genelge rows retrieve against these Chroma document_id values.
SGK_BASELINE_DOCUMENT_IDS = ("law:5510", "law:4447")


class DailyUpdate(BaseModel):
    """One fetched publication, matching the daily_updates JSON schema."""

    source: SourceName
    publication_date: str
    title: str
    category: str
    url: str
    raw_text: str = ""
    fetched_at: str = Field(default_factory=utc_now_iso)
    baseline_document_ids: list[str] = Field(default_factory=list)

    model_config = {"extra": "ignore"}
