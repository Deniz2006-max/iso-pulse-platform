"""Daily legal-source ingestion (Resmî Gazete, SGK, tracked mevzuat)."""

from src.ingestion.daily_cache import DailyRevisionsCache
from src.ingestion.models import SGK_BASELINE_DOCUMENT_IDS, DailyUpdate
from src.ingestion.records import has_valid_cards, is_passed_record

__all__ = [
    "DailyUpdate",
    "SGK_BASELINE_DOCUMENT_IDS",
    "DailyRevisionsCache",
    "has_valid_cards",
    "is_passed_record",
]
