"""SQLite cache of today's processed RG / SGK revisions.

Collection name: ``daily_revisions_cache``

After the first successful daily ingest, Streamlit (and CLI) load analysed
items from this file instead of re-scraping Resmî Gazete / SGK or re-running
LangGraph embeddings.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from config.settings import settings
from src.ingestion.records import is_passed_record

CACHE_TABLE = "daily_revisions_cache"
META_TABLE = "daily_run_meta"


def default_cache_path() -> Path:
    path = Path(getattr(settings, "daily_cache_path", Path("data") / "daily_revisions_cache.sqlite"))
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class CacheStatus:
    """Whether today's run can be served from SQLite without scraping."""

    warm: bool
    day: str
    source: str
    fetched_at: str = ""
    record_count: int = 0
    relevant_count: int = 0
    message: str = ""


class DailyRevisionsCache:
    """Persist pipeline JSON keyed by calendar day + source."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_cache_path()
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure(self) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
                    day TEXT NOT NULL,
                    source TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    url TEXT,
                    title TEXT,
                    is_relevant INTEGER NOT NULL DEFAULT 0,
                    payload_json TEXT NOT NULL,
                    PRIMARY KEY (day, source, document_id)
                )
                """
            )
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {META_TABLE} (
                    day TEXT NOT NULL,
                    source TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    relevant_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    PRIMARY KEY (day, source)
                )
                """
            )
            conn.commit()

    def status(self, day: str, source: str = "all") -> CacheStatus:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT * FROM {META_TABLE} WHERE day = ? AND source = ?",
                (day, source),
            ).fetchone()
        if not row or row["status"] != "complete":
            return CacheStatus(
                warm=False,
                day=day,
                source=source,
                message="No complete daily cache for this date.",
            )
        relevant = int(row["relevant_count"])
        records = int(row["record_count"])
        return CacheStatus(
            warm=True,
            day=day,
            source=source,
            fetched_at=row["fetched_at"],
            record_count=records,
            relevant_count=relevant,
            message=(
                f"Cache hit: {relevant} relevant / {records} processed items "
                f"(saved {row['fetched_at']}). Skipping scrape and re-embed."
            ),
        )

    def load_records(self, day: str, source: str = "all") -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT payload_json FROM {CACHE_TABLE}
                WHERE day = ? AND source = ?
                ORDER BY title
                """,
                (day, source),
            ).fetchall()
        records: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
        return records

    def store_run(
        self,
        day: str,
        source: str,
        records: Iterable[dict[str, Any]],
    ) -> CacheStatus:
        rows = list(records)
        relevant = sum(1 for row in rows if is_passed_record(row))
        fetched_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                f"DELETE FROM {CACHE_TABLE} WHERE day = ? AND source = ?",
                (day, source),
            )
            conn.execute(
                f"DELETE FROM {META_TABLE} WHERE day = ? AND source = ?",
                (day, source),
            )
            for row in rows:
                document_id = str(row.get("document_id") or row.get("url") or row.get("title") or "")
                if not document_id:
                    continue
                conn.execute(
                    f"""
                    INSERT INTO {CACHE_TABLE}
                    (day, source, document_id, url, title, is_relevant, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        day,
                        source,
                        document_id,
                        str(row.get("url") or ""),
                        str(row.get("title") or ""),
                        1 if row.get("is_relevant") else 0,
                        json.dumps(row, ensure_ascii=False, default=str),
                    ),
                )
            conn.execute(
                f"""
                INSERT INTO {META_TABLE}
                (day, source, fetched_at, record_count, relevant_count, status)
                VALUES (?, ?, ?, ?, ?, 'complete')
                """,
                (day, source, fetched_at, len(rows), relevant),
            )
            conn.commit()
        return CacheStatus(
            warm=True,
            day=day,
            source=source,
            fetched_at=fetched_at,
            record_count=len(rows),
            relevant_count=relevant,
            message=f"Cached {relevant} relevant / {len(rows)} processed items for {day}.",
        )

    def purge_all(self) -> None:
        """Delete the SQLite file (and WAL/SHM) so every date must re-run."""
        self.path.unlink(missing_ok=True)
        Path(str(self.path) + "-wal").unlink(missing_ok=True)
        Path(str(self.path) + "-shm").unlink(missing_ok=True)

    def drop_day(self, day: str, source: str | None = None) -> None:
        """Remove cached analysis for a calendar day so the next run scrapes live."""
        with self._connect() as conn:
            if source:
                conn.execute(
                    f"DELETE FROM {CACHE_TABLE} WHERE day = ? AND source = ?",
                    (day, source),
                )
                conn.execute(
                    f"DELETE FROM {META_TABLE} WHERE day = ? AND source = ?",
                    (day, source),
                )
            else:
                conn.execute(f"DELETE FROM {CACHE_TABLE} WHERE day = ?", (day,))
                conn.execute(f"DELETE FROM {META_TABLE} WHERE day = ?", (day,))
            conn.commit()
