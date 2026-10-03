"""Track updates to baseline statutes without crawling mevzuat.gov.tr.

mevzuat.gov.tr blocks automated access (see OKUBENI.md). Nightly refresh of
consolidated kanun PDFs is a manual download + scripts/pdf_to_madde_json.py
step. This module instead:

1. Reads the day's Resmî Gazete yürütme items (Kanun / Yönetmelik / Tebliğ).
2. Keeps those that cite a tracked kanun number (4857, 5510, 6331, 5746, …).
3. Attaches matching local baseline provisions from data/mevzuat/*.json.

Canonical mevzuat.gov.tr URLs are recorded as references only — they are
never fetched.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path

from src.ingestion.client import FetchClient
from src.ingestion.extract import tr_fold
from src.ingestion.models import DailyUpdate, utc_now_iso
from src.ingestion.resmi_gazete import fetch_edition

LOGGER = logging.getLogger("iso_pulse.ingestion.mevzuat")

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MEVZUAT_DIR = ROOT / "data" / "mevzuat"

DEFAULT_KANUN_NOS = (
    "4857",
    "5510",
    "6331",
    "5746",
    "6698",
    "4447",
    "4632",
    "5174",
)

_SAYILI_RE = re.compile(
    r"(\d{3,5})\s*(?:sayılı|sayili)\b",
    re.IGNORECASE,
)
_MADDE_RE = re.compile(
    r"(?:madde|md\.?)\s*(\d+)",
    re.IGNORECASE,
)


def _kanun_no_from_document_id(document_id: str) -> str | None:
    match = re.search(r"law:(\d+)", document_id)
    return match.group(1) if match else None


def load_baseline(mevzuat_dir: Path) -> dict[str, dict]:
    """Map kanun_no → {title, canonical_url, provisions: [{label, text, ...}]}."""
    catalog: dict[str, dict] = {}
    if not mevzuat_dir.is_dir():
        LOGGER.warning("Baseline directory missing: %s", mevzuat_dir)
        return catalog
    for path in sorted(mevzuat_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            LOGGER.warning("Skip unreadable baseline %s: %s", path.name, exc)
            continue
        for doc in payload.get("documents") or []:
            kanun_no = _kanun_no_from_document_id(str(doc.get("document_id") or ""))
            if not kanun_no:
                continue
            catalog[kanun_no] = {
                "kanun_no": kanun_no,
                "title": doc.get("title") or path.stem,
                "canonical_url": doc.get("canonical_url")
                or f"https://www.mevzuat.gov.tr/mevzuat?MevzuatNo={kanun_no}&MevzuatTur=1&MevzuatTertip=5",
                "path": str(path),
                "provisions": [
                    {
                        "provision_id": p.get("provision_id"),
                        "label": p.get("label"),
                        "text": p.get("text") or "",
                        "mulga": bool(p.get("mulga")),
                    }
                    for p in (doc.get("included_provisions") or [])
                ],
            }
    LOGGER.info("Loaded %s baseline statutes from %s", len(catalog), mevzuat_dir)
    return catalog


def cited_kanun_nos(text: str, tracked: set[str], titles: dict[str, str]) -> set[str]:
    hits = {m.group(1) for m in _SAYILI_RE.finditer(text) if m.group(1) in tracked}
    folded = tr_fold(text)
    for kanun_no, title in titles.items():
        if kanun_no not in tracked:
            continue
        needle = tr_fold(title)
        if needle and needle in folded:
            hits.add(kanun_no)
        if tr_fold(f"{kanun_no} SAYILI") in folded:
            hits.add(kanun_no)
    return hits


def cited_madde_labels(text: str) -> set[str]:
    return {f"Madde {m.group(1)}" for m in _MADDE_RE.finditer(text)}


def _attach_baseline(item: DailyUpdate, statutes: list[dict]) -> str:
    parts = [
        item.raw_text.strip(),
        "",
        "--- Yerel baseline (mevzuat.gov.tr crawl yok; OKUBENI.md) ---",
    ]
    wanted_labels = cited_madde_labels(item.raw_text + " " + item.title)
    for statute in statutes:
        parts.append(f"[{statute['title']}] {statute['canonical_url']}")
        matched = []
        for prov in statute["provisions"]:
            if prov.get("mulga"):
                continue
            label = str(prov.get("label") or "")
            if wanted_labels and label not in wanted_labels:
                continue
            matched.append(prov)
        if not wanted_labels:
            # No madde citation — keep a short pointer, not the whole kanun.
            parts.append(
                f"  Yerel dosya: {statute['path']} "
                f"({len(statute['provisions'])} madde). "
                "Tam metin için PDF'i elle indirip pdf_to_madde_json.py çalıştırın."
            )
            continue
        if not matched:
            parts.append("  Anılan maddeler yerel baseline'da bulunamadı.")
            continue
        for prov in matched[:12]:
            parts.append(f"  {prov['label']}: {prov['text']}")
    return "\n".join(parts).strip()


def _mevzuat_url(statutes: list[dict], fallback: str) -> str:
    if len(statutes) == 1:
        return str(statutes[0]["canonical_url"])
    return fallback


async def fetch_updates(
    day: date,
    *,
    kanun_nos: tuple[str, ...] | list[str] | None = None,
    mevzuat_dir: Path | None = None,
    rg_items: list[DailyUpdate] | None = None,
    client: FetchClient | None = None,
) -> list[DailyUpdate]:
    """Return RG items that amend a tracked statute, with local baseline text."""
    tracked = {str(n) for n in (kanun_nos or DEFAULT_KANUN_NOS)}
    catalog = load_baseline(mevzuat_dir or DEFAULT_MEVZUAT_DIR)
    titles = {no: str(meta["title"]) for no, meta in catalog.items()}

    if rg_items is None:
        LOGGER.info(
            "mevzuat.gov.tr will not be fetched; scanning Resmî Gazete %s for %s",
            day.isoformat(),
            sorted(tracked),
        )
        rg_items = await fetch_edition(day, client=client)

    fetched_at = utc_now_iso()
    out: list[DailyUpdate] = []
    seen: set[str] = set()
    for item in rg_items:
        blob = f"{item.title}\n{item.raw_text}"
        hits = cited_kanun_nos(blob, tracked, titles)
        if not hits:
            continue
        if item.url in seen:
            continue
        seen.add(item.url)
        statutes = [catalog[n] for n in sorted(hits) if n in catalog]
        out.append(
            DailyUpdate(
                source="mevzuat",
                publication_date=item.publication_date,
                title=item.title,
                category=item.category if item.category else "Mevzuat Değişikliği",
                url=_mevzuat_url(statutes, item.url),
                raw_text=_attach_baseline(item, statutes) if statutes else item.raw_text,
                fetched_at=fetched_at,
            )
        )

    LOGGER.info(
        "Mevzuat tracker: %s Resmî Gazete items cite tracked kanun numbers",
        len(out),
    )
    return out
