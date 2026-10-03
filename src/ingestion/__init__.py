"""Daily legal-source ingestion (Resmî Gazete, SGK, tracked mevzuat)."""

from src.ingestion.models import SGK_BASELINE_DOCUMENT_IDS, DailyUpdate

__all__ = ["DailyUpdate", "SGK_BASELINE_DOCUMENT_IDS"]
