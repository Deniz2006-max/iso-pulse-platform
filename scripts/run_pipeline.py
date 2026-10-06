#!/usr/bin/env python3
"""Drive daily scraper JSON through the ISO-PULSE LangGraph pipeline.

Filter → Retriever (Chroma `iso_mevzuat_baseline`) → Router → Specialist →
Verifier → Delivery.

Usage (from repository root):

    python3 scripts/run_pipeline.py
    python3 scripts/run_pipeline.py --date 2026-10-01 --source sgk --limit 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.llm import llm_runtime_label, require_openai_api_key, MissingOpenAIKeyError
from config.executive_copy import (
    coerce_executive_summary,
    grounded_action,
    grounded_executive_summary,
    grounded_obligation,
    is_generic_executive_copy,
)
from config.relevance import (
    audience_scope,
    classify_relevance,
    implied_departments,
    is_administrative_out_of_scope,
)
from config.settings import settings
from graph import graph
from schemas.outputs import department_label
from src.ingestion.daily_cache import DailyRevisionsCache
from src.ingestion.day_window import filter_published_today
from src.ingestion.models import SGK_BASELINE_DOCUMENT_IDS, DailyUpdate

LOGGER = logging.getLogger("iso_pulse.pipeline")

TEXT_CAP = 16_000
SOURCE_FILES = {
    "resmi_gazete": "resmi_gazete.json",
    "sgk": "sgk.json",
    "mevzuat": "mevzuat.json",
    "all": "all.json",
}
VALID_SOURCES = ("resmi_gazete", "sgk", "mevzuat", "csgb")


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
    for noisy in ("httpx", "httpcore", "chromadb", "pdfminer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _as_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def daily_updates_dir() -> Path:
    return _as_path(Path(settings.daily_updates_dir))


def reports_dir() -> Path:
    return _as_path(Path(getattr(settings, "reports_dir", ROOT / "data" / "reports")))


def parse_day(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"Invalid --date {value!r}; expected YYYY-MM-DD") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the LangGraph pipeline on scraped daily updates."
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Folder under data/daily_updates/ (default: today)",
    )
    parser.add_argument(
        "--source",
        choices=("resmi_gazete", "sgk", "mevzuat", "all"),
        default="all",
        help="Which scraper JSON to load (default: all)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N items",
    )
    parser.add_argument(
        "--updates-dir",
        type=Path,
        default=None,
        help="Override data/daily_updates root",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=None,
        help="Override data/reports root",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore daily_revisions_cache and re-analyse from scraped JSON.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def load_updates(folder: Path, source: str) -> list[DailyUpdate]:
    rows: list[dict[str, Any]] = []
    if source == "all":
        combined = folder / SOURCE_FILES["all"]
        rows = _load_json_array(combined)
        if not rows:
            for name in ("resmi_gazete.json", "sgk.json", "mevzuat.json"):
                rows.extend(_load_json_array(folder / name))
    else:
        rows = _load_json_array(folder / SOURCE_FILES[source])

    items: list[DailyUpdate] = []
    seen: set[str] = set()
    for row in rows:
        try:
            item = DailyUpdate.model_validate(row)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Skip malformed item: %s", exc)
            continue
        key = item.url or f"{item.source}:{item.title}:{item.raw_text[:80]}"
        if key in seen:
            continue
        seen.add(key)
        if source != "all" and item.source != source:
            continue
        items.append(item)
    return items


def _slug(value: str, fallback: str) -> str:
    ascii_ish = (
        value.replace("ı", "i")
        .replace("İ", "I")
        .replace("ş", "s")
        .replace("Ş", "S")
        .replace("ğ", "g")
        .replace("Ğ", "G")
        .replace("ü", "u")
        .replace("Ü", "U")
        .replace("ö", "o")
        .replace("Ö", "O")
        .replace("ç", "c")
        .replace("Ç", "C")
    )
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_ish).strip("-")
    return (slug[:80] or fallback)


def document_id_for(item: DailyUpdate) -> str:
    digest = hashlib.sha256(
        f"{item.source}|{item.url}|{item.title}".encode("utf-8")
    ).hexdigest()[:12]
    return f"iso:{item.source}:{digest}"


def clip_text(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= TEXT_CAP:
        return text
    return text[:TEXT_CAP] + "\n\n[... truncated for pipeline ...]"


def item_to_state(item: DailyUpdate) -> dict[str, Any]:
    body = clip_text(item.raw_text) or clip_text(item.title)
    source = item.source if item.source in VALID_SOURCES else "resmi_gazete"
    doc_id = document_id_for(item)
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    baselines = list(item.baseline_document_ids or [])
    if source == "sgk" and not baselines:
        baselines = list(SGK_BASELINE_DOCUMENT_IDS)
    return {
        "source": source,
        "document_id": doc_id,
        "title": item.title or doc_id,
        "old_text": None,
        "new_text": body,
        "diff": "",
        "sha256": sha,
        "analyses": {},
        "audit_log": [],
        "baseline_document_ids": baselines,
    }


def _dump(model: Any) -> Any:
    if model is None:
        return None
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    if isinstance(model, list):
        return [_dump(item) for item in model]
    if isinstance(model, dict):
        return {key: _dump(value) for key, value in model.items()}
    return model


def stub_relevant_record(
    item: DailyUpdate,
    state: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    """Keep a passed item visible even if the LLM graph fails."""
    departments = implied_departments(item.title, item.raw_text, state["document_id"]) or [
        "hukuk"
    ]
    scope = audience_scope(item.title, item.raw_text)
    urgency = "low" if scope in {"kamu", "specialized"} else "medium"
    analyses: dict[str, Any] = {}
    for dept in departments:
        analyses[dept] = {
            "department": dept,
            "summary": grounded_executive_summary(item.title, item.raw_text, dept),
            "obligation_change": grounded_obligation(item.title, item.raw_text),
            "operational_impact": grounded_action(dept, item.title, item.raw_text),
            "citations": [],
            "analysis_mode": "fallback",
        }
    return {
        "source": item.source,
        "publication_date": item.publication_date,
        "title": item.title,
        "category": item.category,
        "url": item.url,
        "document_id": state["document_id"],
        "is_relevant": True,
        "relevance_reason": reason,
        "retrieved_provision_id": "",
        "retrieved_chunks": [],
        "old_text": "",
        "departments": departments,
        "needs_review": True,
        "urgency": urgency,
        "sector_scope": scope,
        "analyses": analyses,
        "delivery": {
            "title": item.title,
            "summary": analyses[departments[0]]["summary"],
            "departments": departments,
            "urgency": urgency,
        },
        "error": True,
        "audit_log": [
            {
                "node": "ISO_Relevance_Filter_Node",
                "action": "filter",
                "detail": f"is_relevant=True; passthrough; {reason}",
            }
        ],
    }


def noise_record(item: DailyUpdate, state: dict[str, Any], reason: str) -> dict[str, Any]:
    """Persist a filtered-out row without invoking specialists or embeddings."""
    administrative = is_administrative_out_of_scope(item.title, item.raw_text)
    return {
        "source": item.source,
        "publication_date": item.publication_date,
        "title": item.title,
        "category": "İdari Duyuru / Kapsam Dışı" if administrative else item.category,
        "url": item.url,
        "document_id": state["document_id"],
        "is_relevant": False,
        "relevance_reason": reason,
        "sector_scope": "general",
        "retrieved_provision_id": "",
        "retrieved_chunks": [],
        "old_text": "",
        "departments": [],
        "needs_review": False,
        "analyses": {},
        "audit_log": [
            {
                "node": "ISO_Relevance_Filter_Node",
                "action": "filter",
                "detail": f"is_relevant=False; daily-prefilter; {reason}",
            }
        ],
    }


def record_from_result(item: DailyUpdate, state: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    stub = stub_relevant_record(item, state, result.get("relevance_reason") or "")
    delivery = result.get("delivery")
    verification = result.get("verification")
    analyses = result.get("analyses") or {}
    if not analyses:
        analyses = stub["analyses"]
    departments = result.get("departments") or stub["departments"]
    dumped_delivery = _dump(delivery) or stub["delivery"]
    dumped_delivery = dict(dumped_delivery) if isinstance(dumped_delivery, dict) else {}
    summary = coerce_executive_summary(
        str(dumped_delivery.get("summary") or ""),
        item.title,
        item.raw_text,
        departments[0] if departments else "hukuk",
    )
    dumped_delivery["summary"] = summary or stub["delivery"]["summary"]
    if not dumped_delivery.get("departments"):
        dumped_delivery["departments"] = departments
    analyses_out = {key: _dump(value) for key, value in analyses.items()}
    for key, value in list(analyses_out.items()):
        if not isinstance(value, dict):
            continue
        if is_generic_executive_copy(str(value.get("summary") or "")):
            value["summary"] = grounded_executive_summary(
                item.title, item.raw_text, str(key)
            )
            value["obligation_change"] = grounded_obligation(item.title, item.raw_text)
            value["operational_impact"] = grounded_action(
                str(key), item.title, item.raw_text
            )
            continue
        value["summary"] = coerce_executive_summary(
            str(value.get("summary") or ""),
            item.title,
            item.raw_text,
            str(key),
        )
    scope = str(result.get("sector_scope") or "") or audience_scope(
        item.title, item.raw_text
    )
    if scope in {"kamu", "specialized"}:
        dumped_delivery["urgency"] = "low"
    return {
        "source": item.source,
        "publication_date": item.publication_date,
        "title": item.title,
        "category": item.category,
        "url": item.url,
        "document_id": result.get("document_id") or state["document_id"],
        "is_relevant": True,
        "relevance_reason": result.get("relevance_reason") or stub["relevance_reason"],
        "sector_scope": scope if scope in {"kamu", "specialized"} else "general",
        "retrieved_provision_id": result.get("retrieved_provision_id") or "",
        "retrieved_chunks": result.get("retrieved_chunks") or [],
        "old_text": result.get("old_text") or "",
        "rag_mode": result.get("rag_mode"),
        "rag_confidence": result.get("rag_confidence"),
        "rag_status": result.get("rag_status") or "",
        "rag_reason": result.get("rag_reason") or "",
        "departments": departments,
        "dropped_departments": result.get("dropped_departments") or [],
        "needs_review": bool(result.get("needs_review", False)),
        "hallucination_score": result.get("hallucination_score"),
        "urgency": "low" if scope in {"kamu", "specialized"} else (result.get("urgency") or "medium"),
        "delivery": dumped_delivery,
        "verification": _dump(verification),
        "analyses": analyses_out,
        "audit_log": _dump(result.get("audit_log") or []),
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def build_summary_md(day: date, records: list[dict[str, Any]]) -> str:
    relevant = [row for row in records if row.get("is_relevant")]
    dropped = [row for row in records if not row.get("is_relevant")]
    lines = [
        f"# İSO PULSE — günlük etki özeti ({day.isoformat()})",
        "",
        f"- İşlenen kayıt: **{len(records)}**",
        f"- Sanayi etkisi (filtre geçti): **{len(relevant)}**",
        f"- Gürültü / düşürülen: **{len(dropped)}**",
        "",
    ]
    if not relevant:
        lines.append("_Bugün filtreyi geçen mevzuat değişikliği yok._")
        lines.append("")
        if dropped:
            lines.append("## Düşürülen kayıtlar")
            for row in dropped:
                reason = row.get("relevance_reason") or ""
                lines.append(f"- {row.get('title')} ({row.get('source')}) — {reason}")
            lines.append("")
        return "\n".join(lines)

    lines.append("## Tespit edilen değişiklikler")
    lines.append("")
    for row in relevant:
        delivery = row.get("delivery") or {}
        urgency = delivery.get("urgency_label") or delivery.get("urgency") or "—"
        depts = ", ".join(
            department_label(code)
            for code in (row.get("departments") or delivery.get("departments") or [])
        ) or "—"
        summary = delivery.get("summary") or row.get("relevance_reason") or ""
        provision = row.get("retrieved_provision_id") or "—"
        rag_status = row.get("rag_status") or (
            "RAG" if row.get("rag_mode") == "rag" else "Fallback" if row.get("rag_mode") == "fallback" else "—"
        )
        lines.append(f"### {row.get('title')}")
        lines.append("")
        lines.append(f"- Kaynak: `{row.get('source')}` · kategori: {row.get('category')}")
        lines.append(f"- Aciliyet: **{urgency}** · birimler: {depts}")
        lines.append(f"- Analiz modu: {rag_status}")
        lines.append(f"- Baseline madde (v1.0): `{provision}`")
        if row.get("url"):
            lines.append(f"- URL: {row['url']}")
        if summary:
            lines.append(f"- Özet: {summary}")
        analyses = row.get("analyses") or {}
        for dept, analysis in analyses.items():
            if not isinstance(analysis, dict):
                continue
            impact = analysis.get("obligation_change") or analysis.get("operational_impact") or ""
            if impact:
                lines.append(f"- **{department_label(str(dept))}**: {impact}")
        if row.get("needs_review"):
            lines.append("- ⚠️ `needs_review=true` — doğrulayıcı inceleme istedi.")
        lines.append("")
    return "\n".join(lines)


def _progress(total: int) -> Iterable[Any]:
    try:
        from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

        progress = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        )
        progress.start()
        task_id = progress.add_task("Pipeline", total=total)
        try:
            yield progress, task_id
        finally:
            progress.stop()
    except ImportError:
        yield None, None


def run(args: argparse.Namespace) -> int:
    day = parse_day(args.date)
    updates_root = _as_path(args.updates_dir) if args.updates_dir else daily_updates_dir()
    folder = updates_root / day.isoformat()
    out_root = _as_path(args.reports_dir) if args.reports_dir else reports_dir()
    out_dir = out_root / day.isoformat()

    if not getattr(args, "refresh", False):
        cache = DailyRevisionsCache()
        status = cache.status(day.isoformat(), args.source)
        records = cache.load_records(day.isoformat(), args.source) if status.warm else []
        if status.warm:
            out_dir.mkdir(parents=True, exist_ok=True)
            write_json(out_dir / "items.json", records)
            items_dir = out_dir / "items"
            items_dir.mkdir(parents=True, exist_ok=True)
            for index, row in enumerate(records, start=1):
                name = _slug(str(row.get("document_id") or f"item-{index}"), f"item-{index}")
                write_json(items_dir / f"{name}.json", row)
            (out_dir / "summary.md").write_text(
                build_summary_md(day, records), encoding="utf-8"
            )
            LOGGER.info(status.message)
            return 0

    if not folder.is_dir():
        LOGGER.error("Daily updates folder not found: %s", folder)
        LOGGER.error("Run: python3 -m src.ingestion.fetch_daily_updates --date %s", day.isoformat())
        return 1

    items = load_updates(folder, args.source)
    items = filter_published_today(items, day)
    if args.limit is not None:
        items = items[: max(0, args.limit)]
    LOGGER.info(
        "Loaded %s item(s) from %s (source=%s)",
        len(items),
        folder,
        args.source,
    )
    if not items:
        LOGGER.warning("Nothing to process.")
        out_dir.mkdir(parents=True, exist_ok=True)
        write_json(out_dir / "items.json", [])
        (out_dir / "summary.md").write_text(
            build_summary_md(day, []), encoding="utf-8"
        )
        DailyRevisionsCache().store_run(day.isoformat(), args.source, [])
        return 0

    if settings.use_mock_llm:
        LOGGER.info("LLM: mock")
    else:
        try:
            require_openai_api_key()
        except MissingOpenAIKeyError as exc:
            LOGGER.error("%s", exc)
            return 1
        LOGGER.info("LLM: %s", llm_runtime_label(mock=False))

    records: list[dict[str, Any]] = []
    items_dir = out_dir / "items"
    items_dir.mkdir(parents=True, exist_ok=True)

    progress_iter = _progress(len(items))
    progress, task_id = next(progress_iter)
    try:
        for index, item in enumerate(items, start=1):
            title_preview = (item.title or "(untitled)")[:80]
            LOGGER.info("[%s/%s] %s · %s", index, len(items), item.source, title_preview)
            if not (item.raw_text or "").strip() and not (item.title or "").strip():
                LOGGER.warning("  skip empty item")
                continue
            state = item_to_state(item)
            verdict, reason = classify_relevance(
                item.title,
                item.raw_text,
                state["document_id"],
                source=item.source,
            )
            if verdict == "drop":
                record = noise_record(item, state, reason)
                records.append(record)
                write_json(items_dir / f"{_slug(state['document_id'], 'item')}.json", record)
                LOGGER.info("  dropped (pre-filter): %s", reason)
                if progress is not None:
                    progress.update(task_id, advance=1)
                continue
            try:
                result = graph.invoke(state)
            except Exception:
                LOGGER.exception("  graph.invoke failed for %s", state["document_id"])
                record = stub_relevant_record(
                    item, state, "pipeline_error; passthrough card generated"
                )
                records.append(record)
                write_json(items_dir / f"{_slug(state['document_id'], 'item')}.json", record)
                if progress is not None:
                    progress.update(task_id, advance=1)
                continue

            record = record_from_result(item, state, result)
            records.append(record)
            filename = _slug(record["document_id"], f"item-{index}") + ".json"
            write_json(items_dir / filename, record)
            if record["is_relevant"]:
                LOGGER.info(
                    "  relevant → depts=%s urgency=%s mode=%s provision=%s",
                    ",".join(record.get("departments") or []) or "none",
                    (record.get("delivery") or {}).get("urgency", "—"),
                    record.get("rag_mode") or "n/a",
                    record.get("retrieved_provision_id") or "—",
                )
            else:
                LOGGER.info("  dropped: %s", record.get("relevance_reason") or "not relevant")
            if progress is not None:
                progress.update(task_id, advance=1)
    finally:
        try:
            next(progress_iter, None)
        except StopIteration:
            pass

    write_json(out_dir / "items.json", records)
    summary_path = out_dir / "summary.md"
    summary_path.write_text(build_summary_md(day, records), encoding="utf-8")
    cache_status = DailyRevisionsCache().store_run(day.isoformat(), args.source, records)
    LOGGER.info(
        "Wrote %s JSON item(s) + %s · %s",
        len(records),
        summary_path,
        cache_status.message,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
