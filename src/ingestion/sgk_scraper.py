"""SGK duyuru / genelge scraper.

Primary listing: https://www.sgk.gov.tr/duyuru/
(The /Duyurular path 404s; /Duyuru and /duyuru both work.)

Takes the latest N announcement cards, opens each detail page, and extracts
HTML body text plus any attached PDF via /Download/DownloadFile.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import date, datetime
from urllib.parse import urljoin

import httpx

from src.ingestion.client import FetchClient
from src.ingestion.extract import (
    html_to_text,
    looks_like_pdf,
    pdf_bytes_to_text_async,
    soup_from_html,
)
from src.ingestion.models import SGK_BASELINE_DOCUMENT_IDS, DailyUpdate, utc_now_iso

LOGGER = logging.getLogger("iso_pulse.ingestion.sgk")

LISTING_URLS = (
    "https://www.sgk.gov.tr/duyuru/",
    "https://www.sgk.gov.tr/Duyuru",
    "https://www.sgk.gov.tr/Duyurular",
)
SGK_ORIGIN = "https://www.sgk.gov.tr"

TR_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "agustos": 8,
    "eylül": 9,
    "eylul": 9,
    "ekim": 10,
    "kasım": 11,
    "kasim": 11,
    "aralık": 12,
    "aralik": 12,
}

_ISO_IN_SLUG = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _parse_tr_date(day_s: str, month_s: str, year_s: str) -> str | None:
    try:
        month = TR_MONTHS.get(month_s.strip().lower())
        if not month:
            return None
        return date(int(year_s), month, int(day_s)).isoformat()
    except ValueError:
        return None


def _date_from_slug(href: str) -> str | None:
    match = _ISO_IN_SLUG.search(href)
    if not match:
        return None
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
    except ValueError:
        return None


def _category_from_title(title: str, unit: str) -> str:
    blob = f"{title} {unit}".lower()
    if "genelge" in blob:
        return "Genelge"
    if "karar" in blob:
        return "Karar"
    return "Duyuru"


def parse_listing(html: str, listing_url: str, limit: int = 10) -> list[dict[str, str]]:
    soup = soup_from_html(html)
    cards = soup.select("a.announcement-card")
    if not cards:
        cards = soup.select('a[href*="/duyuru/detay/"]')
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in cards:
        href = (card.get("href") or "").strip()
        if not href:
            continue
        url = urljoin(listing_url, href)
        if url in seen:
            continue
        seen.add(url)
        title_el = card.select_one(".announcement-title")
        unit_el = card.select_one(".announcement-link")
        title = (title_el.get_text(" ", strip=True) if title_el else card.get_text(" ", strip=True)).strip()
        unit = unit_el.get_text(" ", strip=True) if unit_el else ""
        day_el = card.select_one(".date-day")
        month_el = card.select_one(".date-month")
        year_el = card.select_one(".date-year")
        published = None
        if day_el and month_el and year_el:
            published = _parse_tr_date(
                day_el.get_text(strip=True),
                month_el.get_text(strip=True),
                year_el.get_text(strip=True),
            )
        published = published or _date_from_slug(href) or datetime.now().date().isoformat()
        if not title:
            continue
        rows.append(
            {
                "title": title,
                "url": url,
                "unit": unit,
                "publication_date": published,
                "category": _category_from_title(title, unit),
            }
        )
        if len(rows) >= limit:
            break
    LOGGER.info("SGK listing: %s announcements from %s", len(rows), listing_url)
    return rows


async def _load_listing(client: FetchClient) -> tuple[str, str]:
    last_error: Exception | None = None
    for url in LISTING_URLS:
        try:
            html = await client.get_html(url)
            if "announcement-card" in html or "/duyuru/detay/" in html:
                return html, url
            LOGGER.warning("Listing at %s had no announcement cards", url)
        except httpx.HTTPError as exc:
            last_error = exc
            LOGGER.warning("SGK listing %s failed: %s", url, exc)
    if last_error:
        raise last_error
    raise RuntimeError("SGK duyuru listing returned no announcement cards")


async def _pdf_text(client: FetchClient, url: str) -> str:
    body, content_type, status = await client.get_bytes(url)
    if status >= 400:
        return ""
    if looks_like_pdf(content_type, url, body):
        return await pdf_bytes_to_text_async(body)
    return ""


async def _detail_text(client: FetchClient, url: str) -> str:
    html = await client.get_html(url)
    soup = soup_from_html(html)
    chunks: list[str] = []

    title_el = soup.select_one(".announcement-detail-title")
    if title_el:
        chunks.append(title_el.get_text(" ", strip=True))

    # Body copy lives in speak-area blocks outside the chrome; PDF names too.
    for doc in soup.select(".document-item .speak-area"):
        name = doc.get_text(" ", strip=True)
        if name:
            chunks.append(f"[Ek: {name}]")

    for link in soup.select('a[href*="/Download/DownloadFile"]'):
        href = urljoin(SGK_ORIGIN, link.get("href") or "")
        try:
            pdf_text = await _pdf_text(client, href)
        except httpx.HTTPError as exc:
            LOGGER.warning("SGK PDF %s failed: %s", href, exc)
            pdf_text = ""
        if pdf_text:
            chunks.append(pdf_text)

    if len(chunks) <= 1:
        # Fall back to stripped detail HTML if there was no usable PDF.
        for junk in soup.select("nav, header, footer, script, style"):
            junk.decompose()
        chunks.append(html_to_text(str(soup)))

    return "\n\n".join(part for part in chunks if part).strip()


async def fetch_announcements(
    *,
    limit: int = 10,
    client: FetchClient | None = None,
) -> list[DailyUpdate]:
    owns_client = client is None
    if owns_client:
        client = FetchClient()
        await client.__aenter__()
    assert client is not None
    try:
        html, listing_url = await _load_listing(client)
        rows = parse_listing(html, listing_url, limit=limit)
        fetched_at = utc_now_iso()

        async def one(row: dict[str, str]) -> DailyUpdate:
            try:
                raw_text = await _detail_text(client, row["url"])
            except httpx.HTTPError as exc:
                LOGGER.warning("SGK detail %s failed: %s", row["url"], exc)
                raw_text = ""
            return DailyUpdate(
                source="sgk",
                publication_date=row["publication_date"],
                title=row["title"],
                category=row["category"],
                url=row["url"],
                raw_text=raw_text,
                fetched_at=fetched_at,
                baseline_document_ids=list(SGK_BASELINE_DOCUMENT_IDS),
            )

        return list(await asyncio.gather(*(one(row) for row in rows)))
    finally:
        if owns_client:
            await client.__aexit__(None, None, None)
