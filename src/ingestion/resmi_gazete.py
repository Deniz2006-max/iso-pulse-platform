"""Resmî Gazete daily edition scraper.

Index URL pattern (stable for years):
    https://www.resmigazete.gov.tr/eskiler/YYYY/MM/YYYYMMDD.htm

Only items under YÜRÜTME VE İDARE BÖLÜMÜ in these subsections are kept:
Kanunlar, Cumhurbaşkanı Kararları, Cumhurbaşkanlığı Kararnamesi,
Yönetmelikler, Tebliğler. Atama decisions and the ilân section are dropped.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date
from urllib.parse import urljoin

import httpx
from bs4 import Tag

from src.ingestion.client import FetchClient
from src.ingestion.extract import (
    html_to_text,
    looks_like_pdf,
    pdf_bytes_to_text_async,
    soup_from_html,
    tr_fold,
)
from src.ingestion.models import DailyUpdate, utc_now_iso

LOGGER = logging.getLogger("iso_pulse.ingestion.resmi_gazete")

BASE_URL = "https://www.resmigazete.gov.tr/"
ESKILER_BASE = "https://www.resmigazete.gov.tr/eskiler/"

ALLOWED_SECTIONS: dict[str, str] = {
    "KANUNLAR": "Kanun",
    "KANUN": "Kanun",
    "CUMHURBAŞKANI KARARLARI": "Cumhurbaşkanı Kararı",
    "CUMHURBAŞKANLIĞI KARARNAMESİ": "Cumhurbaşkanlığı Kararnamesi",
    "CUMHURBAŞKANLIĞI KARARNAMELERİ": "Cumhurbaşkanlığı Kararnamesi",
    "YÖNETMELİKLER": "Yönetmelik",
    "YÖNETMELİK": "Yönetmelik",
    "TEBLİĞLER": "Tebliğ",
    "TEBLİĞ": "Tebliğ",
}
SKIP_SECTION_MARKERS = (
    "ATAMA KARARLARI",
    "İLÂN BÖLÜMÜ",
    "ILAN BÖLÜMÜ",
    "YARGI İLÂNLARI",
    "YARGI İLANLARI",
)
YURUTME_MARKER = "YÜRÜTME VE İDARE BÖLÜMÜ"
_FOLDED_ALLOWED = {tr_fold(name): category for name, category in ALLOWED_SECTIONS.items()}
_FOLDED_SKIP = tuple(tr_fold(name) for name in SKIP_SECTION_MARKERS)
_FOLDED_YURUTME = tr_fold(YURUTME_MARKER)

_TITLE_PREFIX_RE = re.compile(r"^[–—\-•\s]+")


def edition_index_url(day: date) -> str:
    return (
        f"{ESKILER_BASE}{day.year:04d}/{day.month:02d}/"
        f"{day.strftime('%Y%m%d')}.htm"
    )


def edition_pdf_url(day: date) -> str:
    return (
        f"{ESKILER_BASE}{day.year:04d}/{day.month:02d}/"
        f"{day.strftime('%Y%m%d')}.pdf"
    )


def _clean_title(title: str) -> str:
    title = _TITLE_PREFIX_RE.sub("", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def _is_heading(folded: str) -> str | None:
    if not folded or len(folded) > 80:
        return None
    if folded == _FOLDED_YURUTME or folded.startswith(_FOLDED_YURUTME):
        return "YÜRÜTME"
    for skip in _FOLDED_SKIP:
        if folded == skip or folded.startswith(skip):
            return "SKIP"
    if folded in _FOLDED_ALLOWED:
        return folded
    for name in _FOLDED_ALLOWED:
        if folded.startswith(name) or name.startswith(folded):
            if abs(len(folded) - len(name)) <= 8:
                return name
    return None


def _item_href_ok(href: str, day: date) -> bool:
    if not href or href.startswith("javascript:"):
        return False
    lowered = href.lower()
    if "ilanlar/" in lowered or "ilanlar" in lowered:
        return False
    stamp = day.strftime("%Y%m%d")
    # Full-edition PDF (no "-N" suffix) is the whole gazete, not an item.
    if re.search(rf"{stamp}\.pdf$", lowered):
        return False
    return stamp in lowered and (lowered.endswith(".htm") or lowered.endswith(".html") or lowered.endswith(".pdf") or f"{stamp}-" in lowered)


def parse_index_items(html: str, day: date, index_url: str) -> list[tuple[str, str, str]]:
    """Return (title, absolute_url, category) for allowed yürütme items."""
    soup = soup_from_html(html)
    current_category: str | None = None
    in_yurutme = False
    seen: set[str] = set()
    items: list[tuple[str, str, str]] = []

    root = soup.body or soup
    for element in root.descendants:
        if not isinstance(element, Tag):
            continue
        if element.name in {"script", "style"}:
            continue

        own_text = element.get_text(" ", strip=True) if element.name in {"b", "font", "p", "span", "td", "strong"} else ""
        if own_text and len(list(element.find_all(True))) <= 2:
            marker = _is_heading(tr_fold(own_text))
            if marker == "YÜRÜTME":
                in_yurutme = True
                current_category = None
            elif marker == "SKIP":
                in_yurutme = False
                current_category = None
            elif marker and marker in _FOLDED_ALLOWED:
                in_yurutme = True
                current_category = _FOLDED_ALLOWED[marker]

        if element.name != "a":
            continue
        href = (element.get("href") or "").strip()
        if not _item_href_ok(href, day):
            continue
        if not in_yurutme or not current_category:
            continue
        title = _clean_title(element.get_text(" ", strip=True))
        if not title:
            continue
        url = urljoin(index_url, href)
        if url in seen:
            continue
        seen.add(url)
        items.append((title, url, current_category))

    if not items:
        items = _parse_index_by_proximity(html, day, index_url)
    LOGGER.info("Resmî Gazete index: %s allowed items (from %s)", len(items), index_url)
    return items


def _parse_index_by_proximity(
    html: str, day: date, index_url: str
) -> list[tuple[str, str, str]]:
    """Fallback: assign each item link the nearest preceding section heading."""
    soup = soup_from_html(html)
    stamp = day.strftime("%Y%m%d")
    pieces: list[tuple[str, Tag | None]] = []
    root = soup.body or soup
    for element in root.descendants:
        if not isinstance(element, Tag):
            continue
        if element.name in {"b", "font", "p", "span", "td", "strong"}:
            folded = tr_fold(element.get_text(" ", strip=True))
            marker = _is_heading(folded)
            if marker:
                pieces.append((marker, None))
        if element.name == "a":
            href = (element.get("href") or "").strip()
            if stamp not in href.lower():
                continue
            pieces.append(("LINK", element))

    current_category: str | None = None
    in_yurutme = False
    items: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for kind, tag in pieces:
        if kind == "YÜRÜTME":
            in_yurutme = True
            current_category = None
            continue
        if kind == "SKIP":
            in_yurutme = False
            current_category = None
            continue
        if kind in _FOLDED_ALLOWED:
            in_yurutme = True
            current_category = _FOLDED_ALLOWED[kind]
            continue
        if kind != "LINK" or tag is None:
            continue
        href = (tag.get("href") or "").strip()
        if not _item_href_ok(href, day) or not in_yurutme or not current_category:
            continue
        title = _clean_title(tag.get_text(" ", strip=True))
        url = urljoin(index_url, href)
        if not title or url in seen:
            continue
        seen.add(url)
        items.append((title, url, current_category))
    return items


async def _extract_body(client: FetchClient, url: str) -> str:
    body, content_type, status = await client.get_bytes(url)
    if status >= 400:
        LOGGER.warning("Item fetch failed %s → %s", url, status)
        return ""
    if looks_like_pdf(content_type, url, body):
        return await pdf_bytes_to_text_async(body)
    html = body.decode("cp1254", errors="replace")
    if "charset" in (content_type or "").lower() or b"charset" in body[:2048].lower():
        from src.ingestion.client import decode_html_bytes

        html = decode_html_bytes(body, content_type, default="cp1254")
    return html_to_text(html)


async def fetch_edition(
    day: date,
    *,
    client: FetchClient | None = None,
    max_items: int | None = None,
) -> list[DailyUpdate]:
    """Scrape one Resmî Gazete edition into DailyUpdate records."""
    owns_client = client is None
    if owns_client:
        client = FetchClient()
        await client.__aenter__()
    assert client is not None
    try:
        index_url = edition_index_url(day)
        try:
            html = await client.get_html(index_url, default_encoding="cp1254")
        except httpx.HTTPError as exc:
            LOGGER.warning("HTML index missing (%s); trying full-edition PDF", exc)
            return await _fetch_full_pdf_fallback(client, day)

        parsed = parse_index_items(html, day, index_url)
        if max_items is not None:
            parsed = parsed[: max(0, max_items)]
        if not parsed:
            LOGGER.warning("No yürütme items parsed from %s", index_url)
            return []

        fetched_at = utc_now_iso()
        publication_date = day.isoformat()

        async def one(title: str, url: str, category: str) -> DailyUpdate:
            try:
                raw_text = await _extract_body(client, url)
            except httpx.HTTPError as exc:
                LOGGER.warning("Failed to fetch %s: %s", url, exc)
                raw_text = ""
            return DailyUpdate(
                source="resmi_gazete",
                publication_date=publication_date,
                title=title,
                category=category,
                url=url,
                raw_text=raw_text,
                fetched_at=fetched_at,
            )

        return list(await asyncio.gather(*(one(*row) for row in parsed)))
    finally:
        if owns_client:
            await client.__aexit__(None, None, None)


async def _fetch_full_pdf_fallback(client: FetchClient, day: date) -> list[DailyUpdate]:
    url = edition_pdf_url(day)
    try:
        body, content_type, status = await client.get_bytes(url)
    except httpx.HTTPError as exc:
        LOGGER.error("Neither HTML nor PDF edition available for %s: %s", day, exc)
        return []
    if status >= 400 or not looks_like_pdf(content_type, url, body):
        LOGGER.error("PDF edition unavailable for %s (%s)", day, status)
        return []
    text = await pdf_bytes_to_text_async(body)
    return [
        DailyUpdate(
            source="resmi_gazete",
            publication_date=day.isoformat(),
            title=f"{day.isoformat()} tarihli Resmî Gazete (tam sayı PDF)",
            category="Resmî Gazete",
            url=url,
            raw_text=text,
        )
    ]
