#!/usr/bin/env python3
"""Run Resmî Gazete, SGK, and mevzuat trackers and persist daily JSON.

Usage (from repository root):

    python3 -m src.ingestion.fetch_daily_updates
    python3 -m src.ingestion.fetch_daily_updates --date 2026-10-01 --source sgk
    python3 src/ingestion/fetch_daily_updates.py --source all --max-items 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.client import FetchClient
from src.ingestion.change_tracking import track_changes, write_json_atomic
from src.ingestion.mevzuat_scraper import DEFAULT_KANUN_NOS, fetch_updates as fetch_mevzuat
from src.ingestion.models import DailyUpdate
from src.ingestion.resmi_gazete import fetch_edition
from src.ingestion.sgk_scraper import fetch_announcements

CORE_SOURCES = ("resmi_gazete", "sgk")

LOGGER = logging.getLogger("iso_pulse.ingestion")

SOURCES = ("resmi_gazete", "sgk", "mevzuat", "all")


def _daily_updates_dir() -> Path:
    try:
        from config.settings import settings

        path = Path(getattr(settings, "daily_updates_dir", ROOT / "data" / "daily_updates"))
    except Exception:  # noqa: BLE001 — settings is optional for this CLI
        path = ROOT / "data" / "daily_updates"
    if not path.is_absolute():
        path = ROOT / path
    return path


def configure_logging(verbose: bool) -> None:
    try:
        from rich.logging import RichHandler

        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format="%(message)s",
            datefmt="%H:%M:%S",
            handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
        )
    except ImportError:
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
    for noisy in (
        "httpx",
        "httpcore",
        "pdfminer",
        "pdfminer.pdfinterp",
        "pdfminer.pdfpage",
        "pdfminer.psparser",
        "pdfminer.pdfdocument",
        "pdfminer.converter",
        "pypdf",
        "pdfplumber",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch daily legal updates into data/daily_updates/YYYY-MM-DD/"
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Edition date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--source",
        choices=SOURCES,
        default="all",
        help="Which scraper to run (default: all = resmi_gazete + sgk)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Override output root (default: data/daily_updates)",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Cap items per source (SGK still defaults to 10 when unset)",
    )
    parser.add_argument(
        "--kanun-no",
        action="append",
        dest="kanun_nos",
        default=None,
        help="Tracked kanun number for the mevzuat tracker (repeatable)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def parse_day(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid --date {value!r}; expected YYYY-MM-DD") from exc


def dump_items(path: Path, items: list[DailyUpdate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [item.model_dump() for item in items]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LOGGER.info("Wrote %s (%s records)", path, len(items))


async def run(args: argparse.Namespace) -> int:
    day = parse_day(args.date)
    out_root = args.out_dir or _daily_updates_dir()
    out_dir = out_root / day.isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    wanted = {args.source} if args.source != "all" else {"resmi_gazete", "sgk", "mevzuat"}
    # Daily payload always includes both official crawlers when source=all.
    if args.source == "all":
        wanted.update(CORE_SOURCES)
    sgk_limit = args.max_items if args.max_items is not None else 10
    kanun_nos = tuple(args.kanun_nos) if args.kanun_nos else DEFAULT_KANUN_NOS

    collected: dict[str, list[DailyUpdate]] = {}
    collection_failures: dict[str, str] = {}
    async with FetchClient() as client:
        collected = await fetch_core_sources(
            day,
            client=client,
            wanted=wanted,
            max_items=args.max_items,
            sgk_limit=sgk_limit,
            failures=collection_failures,
        )
        for source, items in collected.items():
            dump_items(out_dir / f"{source}.json", items)

        if "mevzuat" in wanted:
            LOGGER.info("Tracking mevzuat changes via Resmî Gazete + local baseline")
            try:
                if "resmi_gazete" in collection_failures:
                    raise RuntimeError("Mevzuat tracking requires a successful RG collection")
                mevzuat_items = await fetch_mevzuat(
                    day,
                    kanun_nos=kanun_nos,
                    rg_items=collected.get("resmi_gazete") or [],
                    client=client,
                )
                collected["mevzuat"] = mevzuat_items
                dump_items(out_dir / "mevzuat.json", mevzuat_items)
            except Exception as exc:  # noqa: BLE001 — keep the other source captures
                collection_failures["mevzuat"] = type(exc).__name__
                LOGGER.error("mevzuat failed: %s", exc)
                collected["mevzuat"] = []
                dump_items(out_dir / "mevzuat.json", [])

    daily_payload = combine_daily_payload(collected)
    dump_items(out_dir / "all.json", daily_payload)

    tracked_items = combine_tracked_payload(collected)
    change_report = track_changes(
        tracked_items,
        state_path=out_root / ".change_tracking" / "state.json",
        run_date=day.isoformat(),
    )
    unconfirmed_sources = sorted(
        source for source in wanted
        if source not in collection_failures and not collected.get(source)
        and (source in CORE_SOURCES or args.source == "mevzuat")
    )
    change_report["collection"] = {
        "requested_sources": sorted(wanted),
        "observed_records": {
            source: len(collected.get(source, [])) for source in sorted(wanted)
        },
        "failed_sources": collection_failures,
        "unconfirmed_sources": unconfirmed_sources,
        "partial": bool(collection_failures or unconfirmed_sources
                        or change_report["counts"]["unverified"]),
        "coverage": "Only the requested edition and sampled listing records were examined",
    }
    change_report_path = out_dir / "change_report.json"
    write_json_atomic(change_report_path, change_report)
    LOGGER.info(
        "Change tracking: %s new, %s changed, %s unchanged, %s unverified -> %s",
        change_report["counts"]["new"],
        change_report["counts"]["changed"],
        change_report["counts"]["unchanged"],
        change_report["counts"]["unverified"],
        change_report_path,
    )

    LOGGER.info("Ingestion summary %s", day.isoformat())
    for source, items in collected.items():
        LOGGER.info("  %s: %s records", source, len(items))
    LOGGER.info(
        "  daily payload (resmi_gazete + sgk): %s -> %s",
        len(daily_payload),
        out_dir / "all.json",
    )
    return 1 if collection_failures else 0


def combine_daily_payload(collected: dict[str, list[DailyUpdate]]) -> list[DailyUpdate]:
    """RG + SGK rows, each keeping its `source` tag. Mevzuat tracker is separate."""
    combined: list[DailyUpdate] = []
    seen: set[str] = set()
    for source in CORE_SOURCES:
        for item in collected.get(source) or []:
            key = item.url or f"{item.source}:{item.title}"
            if key in seen:
                continue
            seen.add(key)
            combined.append(item)
    return combined


def combine_tracked_payload(collected: dict[str, list[DailyUpdate]]) -> list[DailyUpdate]:
    """Collect observed records from every requested source for comparison."""
    combined: list[DailyUpdate] = []
    seen: set[str] = set()
    for source, items in collected.items():
        for item in items:
            key = f"{source}:{item.url or item.title}"
            if key in seen:
                continue
            seen.add(key)
            combined.append(item)
    return combined


async def _safe_fetch(
    label: str,
    coro,
    *,
    failures: dict[str, str] | None = None,
) -> list[DailyUpdate]:
    try:
        items = await coro
        LOGGER.info("%s: %s records", label, len(items))
        return items
    except Exception as exc:  # noqa: BLE001 — one source must not abort the other
        LOGGER.error("%s failed: %s", label, exc)
        if failures is not None:
            failures[label] = type(exc).__name__
        return []


async def fetch_core_sources(
    day,
    *,
    client: FetchClient,
    wanted: set[str],
    max_items: int | None,
    sgk_limit: int,
    failures: dict[str, str] | None = None,
) -> dict[str, list[DailyUpdate]]:
    """Run Resmî Gazete and SGK crawlers in parallel when both are requested."""
    tasks: dict[str, asyncio.Task[list[DailyUpdate]]] = {}
    if "resmi_gazete" in wanted:
        LOGGER.info("Scraping Resmî Gazete %s", day.isoformat())
        tasks["resmi_gazete"] = asyncio.create_task(
            _safe_fetch(
                "resmi_gazete",
                fetch_edition(day, client=client, max_items=max_items),
                failures=failures,
            )
        )
    if "sgk" in wanted:
        LOGGER.info("Scraping SGK duyuru/genelge (latest %s)", sgk_limit)
        tasks["sgk"] = asyncio.create_task(
            _safe_fetch(
                "sgk",
                fetch_announcements(limit=sgk_limit, client=client),
                failures=failures,
            )
        )
    collected: dict[str, list[DailyUpdate]] = {}
    for source, task in tasks.items():
        items = await task
        tagged: list[DailyUpdate] = []
        for item in items:
            updates: dict = {}
            if item.source != source:
                updates["source"] = source
            if source == "sgk" and not item.baseline_document_ids:
                from src.ingestion.models import SGK_BASELINE_DOCUMENT_IDS

                updates["baseline_document_ids"] = list(SGK_BASELINE_DOCUMENT_IDS)
            tagged.append(item.model_copy(update=updates) if updates else item)
        collected[source] = tagged
    return collected


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        LOGGER.warning("Interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
