"""Daily ingest orchestrator: date-specific scrape → relevance filter → cache.

Presentation path
-----------------
1. If ``daily_revisions_cache`` already holds a complete run for this date,
   return it immediately (no Resmî Gazete/SGK HTTP, no BGE-M3 re-embed).
2. Otherwise scrape items published on this calendar day from 00:00,
   drop only personal AYM petitions and job ads, run LangGraph, then cache.

CLI::

    python3 -m src.ingestion.daily_pipeline
    python3 -m src.ingestion.daily_pipeline --refresh
    python3 -m src.ingestion.daily_pipeline --date 2026-10-06 --source all
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.daily_cache import CacheStatus, DailyRevisionsCache
from src.ingestion.records import STALE_DEMO_DAYS, is_passed_record

LOGGER = logging.getLogger("iso_pulse.ingestion.daily_pipeline")


@dataclass
class DailyIngestResult:
    """Outcome of :func:`ensure_today` — cache hit or a freshly built run."""

    day: str
    source: str
    cache_hit: bool
    records: list[dict[str, Any]] = field(default_factory=list)
    status: CacheStatus | None = None
    fetch_code: int = 0
    pipeline_code: int = 0
    message: str = ""

    @property
    def relevant_count(self) -> int:
        return sum(1 for row in self.records if is_passed_record(row))

    @property
    def ok(self) -> bool:
        return self.fetch_code == 0 and self.pipeline_code == 0


def ensure_today(
    day: date | str | None = None,
    source: str = "all",
    *,
    force: bool = False,
    limit: int | None = None,
    fast_mock: bool | None = None,
    cache: DailyRevisionsCache | None = None,
) -> DailyIngestResult:
    """Return analysed revisions for the selected calendar day.

    Uses SQLite ``daily_revisions_cache`` when that date is already complete.
    Otherwise scrapes Resmî Gazete and SGK for the target date from 00:00.
    """
    if isinstance(day, str):
        day_s = day
        day_d = datetime.strptime(day, "%Y-%m-%d").date()
    else:
        day_d = day or date.today()
        day_s = day_d.isoformat()
    source = source or "all"
    store = cache or DailyRevisionsCache()

    if not force:
        status = store.status(day_s, source)
        if status.warm:
            records = store.load_records(day_s, source)
            restore_reports(day_s, records)
            LOGGER.info(status.message)
            return DailyIngestResult(
                day=day_s,
                source=source,
                cache_hit=True,
                records=records,
                status=status,
                message=status.message,
            )

    LOGGER.info(
        "Cache miss for %s / %s — scraping publications from 00:00 %s",
        day_s,
        source,
        day_s,
    )
    fetch_code = _run_fetch(day_s, source, limit)
    if fetch_code != 0:
        msg = f"Scraper failed for {day_s} (exit {fetch_code})."
        LOGGER.error(msg)
        return DailyIngestResult(
            day=day_s,
            source=source,
            cache_hit=False,
            fetch_code=fetch_code,
            pipeline_code=1,
            message=msg,
        )

    pipeline_code = _run_pipeline(day_s, source, limit, fast_mock, refresh=force)
    if pipeline_code != 0:
        msg = f"Pipeline failed for {day_s} (exit {pipeline_code})."
        LOGGER.error(msg)
        return DailyIngestResult(
            day=day_s,
            source=source,
            cache_hit=False,
            fetch_code=fetch_code,
            pipeline_code=pipeline_code,
            message=msg,
        )

    records = _load_report_records(day_s)
    status = store.store_run(day_s, source, records)
    return DailyIngestResult(
        day=day_s,
        source=source,
        cache_hit=False,
        records=records,
        status=status,
        fetch_code=fetch_code,
        pipeline_code=pipeline_code,
        message=status.message,
    )


def _run_fetch(day: str, source: str, limit: int | None) -> int:
    from src.ingestion.fetch_daily_updates import main as fetch_main

    argv = ["--date", day, "--source", source]
    if limit is not None:
        argv.extend(["--max-items", str(limit)])
    return fetch_main(argv)


def _run_pipeline(
    day: str,
    source: str,
    limit: int | None,
    fast_mock: bool | None,
    *,
    refresh: bool = False,
) -> int:
    import os

    if fast_mock is True:
        os.environ["ISO_PULSE_USE_MOCK_LLM"] = "true"
    elif fast_mock is False:
        os.environ["ISO_PULSE_USE_MOCK_LLM"] = "false"
        from config.llm import require_openai_api_key

        require_openai_api_key()
    from scripts.run_pipeline import main as pipeline_main

    argv = ["--date", day, "--source", source]
    if limit is not None:
        argv.extend(["--limit", str(limit)])
    if refresh:
        argv.append("--refresh")
    return pipeline_main(argv)


def _reports_dir(day: str) -> Path:
    from config.settings import settings

    root = Path(settings.reports_dir)
    if not root.is_absolute():
        root = ROOT / root
    return root / day


def _load_report_records(day: str) -> list[dict[str, Any]]:
    import json

    path = _reports_dir(day) / "items.json"
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def restore_reports(day: str, records: list[dict[str, Any]]) -> None:
    """If JSON reports were deleted, rebuild them from the SQLite cache."""
    from scripts.run_pipeline import build_summary_md, write_json

    folder = _reports_dir(day)
    items_json = folder / "items.json"
    if items_json.is_file():
        return
    folder.mkdir(parents=True, exist_ok=True)
    items_dir = folder / "items"
    items_dir.mkdir(parents=True, exist_ok=True)
    write_json(items_json, records)
    for index, row in enumerate(records, start=1):
        name = str(row.get("document_id") or f"item-{index}").replace(":", "-")
        write_json(items_dir / f"{name}.json", row)
    day_d = datetime.strptime(day, "%Y-%m-%d").date()
    (folder / "summary.md").write_text(
        build_summary_md(day_d, records), encoding="utf-8"
    )


def clear_cached_days(
    days: list[str] | None = None,
    *,
    cache: DailyRevisionsCache | None = None,
) -> None:
    """Drop SQLite rows and on-disk reports so the next analysis uses a live filter."""
    store = cache or DailyRevisionsCache()
    for day in days or list(STALE_DEMO_DAYS):
        store.drop_day(day)
        folder = _reports_dir(day)
        if folder.is_dir():
            shutil.rmtree(folder)
        updates = ROOT / "data" / "daily_updates" / day
        if updates.is_dir():
            shutil.rmtree(updates)
        LOGGER.info("Cleared cache and reports for %s", day)


def wipe_all_cached_analysis(*, cache: DailyRevisionsCache | None = None) -> None:
    """Completely remove the daily SQLite cache and generated reports/scrapes."""
    from config.settings import settings

    store = cache or DailyRevisionsCache()
    store.purge_all()
    reports = Path(settings.reports_dir)
    if not reports.is_absolute():
        reports = ROOT / reports
    if reports.is_dir():
        for child in reports.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    updates = ROOT / "data" / "daily_updates"
    if updates.is_dir():
        for child in updates.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    LOGGER.info("Wiped daily_revisions_cache.sqlite and all dated reports/scrapes.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ingest Resmî Gazete + SGK items for a calendar day (from 00:00), "
            "filter industrial relevance, analyse, and cache."
        )
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument(
        "--source",
        choices=("resmi_gazete", "sgk", "mevzuat", "all"),
        default="all",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore SQLite cache and scrape + analyse again.",
    )
    parser.add_argument(
        "--fast-mock",
        action="store_true",
        help="Force ISO_PULSE_USE_MOCK_LLM=true for a quick demo run.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    result = ensure_today(
        args.date,
        args.source,
        force=args.refresh,
        limit=args.limit,
        fast_mock=True if args.fast_mock else None,
    )
    LOGGER.info(result.message)
    LOGGER.info(
        "day=%s cache_hit=%s relevant=%s total=%s",
        result.day,
        result.cache_hit,
        result.relevant_count,
        len(result.records),
    )
    return 0 if result.ok else (result.pipeline_code or result.fetch_code or 1)


if __name__ == "__main__":
    raise SystemExit(main())
