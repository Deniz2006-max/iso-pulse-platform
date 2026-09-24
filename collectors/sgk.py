"""Bounded, evidence-first collection of SGK announcement pages."""

from __future__ import annotations

import re
from datetime import date
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

from collectors.common import CollectionError, canonical_json, sha256_bytes

BASE_URL = "https://www.sgk.gov.tr"
UNIT = "TumBirimler"
HEADERS = {"User-Agent": "ISO-Pulse/0.1 (official-announcement collector)"}
MONTHS = {name: number for number, name in enumerate(
    ("Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
     "Eylül", "Ekim", "Kasım", "Aralık"), start=1)}
SLUG_TIMESTAMP = re.compile(r"-(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})$")
UUID_PATTERN = r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
FILE_NAME = re.compile(rf"^({UUID_PATTERN})\.([a-zA-Z0-9]{{1,8}})$")
UUID = re.compile(rf"^{UUID_PATTERN}$")


def listing_url(page: int) -> str:
    if page < 1:
        raise ValueError("SGK page must be at least 1; page 0 aliases page 1")
    return f"{BASE_URL}/duyuru/index/{UNIT}?page={page}"


def _decode(raw: bytes, media_type: str, charset: str | None, url: str) -> str:
    if media_type != "text/html" or not raw:
        raise CollectionError(f"{url}: expected nonempty HTML, got {media_type}")
    try:
        return raw.decode(charset or "utf-8")
    except (LookupError, UnicodeDecodeError) as exc:
        raise CollectionError(f"{url}: cannot decode HTML") from exc


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    return set(dict(attrs).get("class", "").split())


def _official_url(href: str, prefix: str) -> str:
    url = urljoin(BASE_URL, href)
    parts = urlparse(url)
    if parts.scheme != "https" or parts.netloc != "www.sgk.gov.tr" or not parts.path.lower().startswith(prefix.lower()):
        raise CollectionError(f"unexpected SGK link: {href}")
    return url


class _ListingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a" and "announcement-card" in _classes(attrs):
            href = dict(attrs).get("href")
            if href:
                self.links.append(_official_url(href, "/duyuru/detay/"))


def parse_listing(raw: bytes, media_type: str, charset: str | None, url: str) -> list[str]:
    parser = _ListingParser()
    parser.feed(_decode(raw, media_type, charset, url))
    if not parser.links or len(parser.links) > 50 or len(set(parser.links)) != len(parser.links):
        raise CollectionError(f"{url}: empty, implausible, or duplicate detail links")
    return parser.links


class _DetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, set[str]]] = []
        self.parts: dict[str, list[str]] = {"title": [], "unit": [], "date": [], "body": []}
        self.captures: dict[str, int] = {}
        self.attachments: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = _classes(attrs)
        if tag in {"br", "hr", "img", "input", "link", "meta", "source"}:
            if tag == "br":
                for field in self.captures:
                    self.parts[field].append(" ")
            return
        self.stack.append((tag, classes))
        if tag == "h1" and any("announcement-detail-title" in group for _, group in self.stack[:-1]):
            self.captures["title"] = len(self.stack)
        elif tag == "span" and "announcement-detail-subtitle" in classes:
            self.captures["unit"] = len(self.stack)
        elif tag == "span" and "announcement-detail-date" in classes:
            self.captures["date"] = len(self.stack)
        elif tag == "div" and {"speak-area", "text-left"} <= classes:
            self.captures["body"] = len(self.stack)
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if urlparse(href).path.lower() == "/download/downloadfile":
                self.attachments.append(_official_url(href, "/Download/DownloadFile"))

    def handle_data(self, data: str) -> None:
        for field in self.captures:
            self.parts[field].append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            return
        if self.stack[-1][0] != tag:
            return
        for field, depth in list(self.captures.items()):
            if depth == len(self.stack):
                del self.captures[field]
            elif tag in {"p", "div", "li"}:
                self.parts[field].append(" ")
        self.stack.pop()


def _published_date(value: str, url: str) -> str:
    match = re.search(r"\b(\d{1,2})\s+([A-Za-zÇĞİÖŞÜçğıöşü]+)\s+(\d{4})\b", value)
    if not match or match.group(2) not in MONTHS:
        raise CollectionError(f"{url}: missing Turkish publication date")
    try:
        return date(int(match.group(3)), MONTHS[match.group(2)], int(match.group(1))).isoformat()
    except ValueError as exc:
        raise CollectionError(f"{url}: invalid publication date") from exc


def attachment_info(url: str) -> dict[str, str]:
    parts = urlparse(_official_url(url, "/Download/DownloadFile"))
    query = parse_qs(parts.query)
    file_value = query.get("f", [""])[0]
    document_value = query.get("d", [""])[0]
    match = FILE_NAME.fullmatch(file_value)
    if not match or not UUID.fullmatch(document_value) or len(query.get("f", [])) != 1 or len(query.get("d", [])) != 1:
        raise CollectionError(f"malformed SGK attachment URL: {url}")
    return {"url": url, "file_token": match.group(1), "document_token": document_value,
            "extension": match.group(2).lower()}


def parse_detail(raw: bytes, media_type: str, charset: str | None, url: str) -> dict[str, Any]:
    parser = _DetailParser()
    parser.feed(_decode(raw, media_type, charset, url))
    fields = {field: " ".join("".join(parts).split()) for field, parts in parser.parts.items()}
    if not fields["title"] or not fields["unit"] or not fields["date"]:
        raise CollectionError(f"{url}: missing SGK title, publishing unit, or displayed date")
    if fields["unit"].upper() in {"ANA SAYFA", "DUYURULAR", "KURUMSAL", "MENÜ"}:
        raise CollectionError(f"{url}: navigation text mistaken for publishing unit")
    if not fields["body"] and not parser.attachments:
        raise CollectionError(f"{url}: no announcement body or attachments")
    if len(set(parser.attachments)) != len(parser.attachments):
        raise CollectionError(f"{url}: duplicate attachment URLs")
    slug = urlparse(url).path.rsplit("/", 1)[-1]
    timestamp = SLUG_TIMESTAMP.search(slug)
    return {"source": "sgk", "source_record_id": urlparse(url).path, "canonical_url": url,
            "title": fields["title"], "publishing_unit": fields["unit"],
            "displayed_date": fields["date"], "source_published_at": _published_date(fields["date"], url),
            "url_embedded_timestamp": "-".join(timestamp.groups()) if timestamp else None,
            "body_text": fields["body"], "detail_raw_sha256": sha256_bytes(raw),
            "attachments": [attachment_info(item) for item in parser.attachments]}


def compare_announcements(previous: dict[str, Any] | None, current: list[dict[str, Any]]) -> dict[str, Any]:
    old = {item["source_record_id"]: item for item in previous["records"]} if previous else {}
    seen: set[str] = set()
    counts: dict[str, int] = {}
    changes: list[dict[str, str]] = []
    for item in current:
        key = item["source_record_id"]
        if key in seen:
            raise CollectionError(f"duplicate SGK announcement: {key}")
        seen.add(key)
        before = old.get(key)
        if before is None:
            status = "baseline_created" if previous is None else "new"
        else:
            if "attachment_text_set_sha256" not in before:
                # First pilot used one mixed raw/text fingerprint. Recompute from
                # its retained attachment records; do not invent a source change.
                old_raw_set = sha256_bytes(canonical_json(sorted(
                    (part["url"], part["raw_sha256"]) for part in before["attachments"])))
                old_text_set = sha256_bytes(canonical_json(sorted(
                    (part["url"], part["normalized_sha256"]) for part in before["attachments"])))
            else:
                old_raw_set = before["attachment_set_sha256"]
                old_text_set = before["attachment_text_set_sha256"]
            detail_changed = before["normalized_sha256"] != item["normalized_sha256"]
            attachments_changed = old_raw_set != item["attachment_set_sha256"]
            detail_extraction_changed = (detail_changed and
                before["detail_raw_sha256"] == item["detail_raw_sha256"])
            attachment_extraction_changed = (not attachments_changed and
                old_text_set != item["attachment_text_set_sha256"])
            if detail_changed and attachments_changed:
                status = "detail_and_attachments_changed"
            elif detail_extraction_changed or attachment_extraction_changed:
                status = "extraction_changed"
            elif detail_changed:
                status = "detail_text_changed"
            elif attachments_changed:
                status = "attachments_changed"
            elif before["detail_raw_sha256"] != item["detail_raw_sha256"]:
                status = "raw_html_changed_only"
            else:
                status = "unchanged"
        item["change_status"] = status
        counts[status] = counts.get(status, 0) + 1
        changes.append({"source_record_id": key, "status": status})
    return {"counts": counts, "changes": changes,
            "missing_prior_ids": sorted(set(old) - seen),
            "missing_prior_note": "Outside the observed page is not a withdrawal or deletion."}
