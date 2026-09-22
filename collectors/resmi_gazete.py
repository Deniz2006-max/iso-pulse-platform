"""Resmî Gazete item-level discovery through the public date filter."""

from __future__ import annotations

import hashlib
import io
import re
import unicodedata
from datetime import date
from html.parser import HTMLParser
from typing import Any, Protocol
from urllib.parse import urljoin, urlparse

from collectors.common import CollectionError, canonical_json, parse_json_object, sha256_bytes, utc_now

FILTER_URL = "https://www.resmigazete.gov.tr/Home/Filter"
BASE_URL = "https://www.resmigazete.gov.tr/"
PAGE_SIZE = 100
INTERMEDIATE_URL = "https://cacerts.digicert.com/GeoTrustTLSRSACAG1.crt.pem"
INTERMEDIATE_DER_SHA256 = "c06e307f7cfc1d32fa72a4c033c87b90019af216f0775d64978a2eca6c8a230e"
HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": BASE_URL,
    "User-Agent": "ISO-Pulse/0.1 (official-publication collector)",
}


class JsonPoster(Protocol):
    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> bytes: ...


class HtmlGetter(Protocol):
    def get(self, url: str, headers: dict[str, str] | None = None) -> tuple[bytes, str, str | None]: ...


class _FihristLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.fragments: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.fragments = []

    def handle_data(self, data: str) -> None:
        if self.href is not None:
            self.fragments.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.href is not None:
            self.links.append((self.href, " ".join(" ".join(self.fragments).split())))
            self.href = None
            self.fragments = []


class _BodyText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "body":
            self.in_body = True
        if tag in {"script", "style"}:
            self.skip_depth += 1
        if tag in {"p", "div", "br", "tr", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1
        if tag == "body":
            self.in_body = False
        if tag in {"p", "div", "tr", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_body and not self.skip_depth:
            self.parts.append(data)


def _title_key(value: str) -> str:
    value = value.replace("ı", "i").replace("İ", "I")
    value = unicodedata.normalize("NFKD", value).casefold()
    return "".join(char for char in value if char.isalnum())


def parse_fihrist_links(raw: bytes, *, day: date, issue_url: str, charset: str | None) -> dict[str, str]:
    if charset is None:
        match = re.search(br"charset\s*=\s*['\"]?([\w-]+)", raw[:4096], re.I)
        charset = match.group(1).decode("ascii") if match else "utf-8"
    try:
        text = raw.decode(charset)
    except (LookupError, UnicodeDecodeError) as exc:
        raise CollectionError(f"{issue_url}: cannot decode fihrist as {charset}") from exc
    parser = _FihristLinks()
    parser.feed(text)
    pattern = re.compile(rf"/eskiler/{day:%Y}/{day:%m}/{day:%Y%m%d}-\d+\.(?:htm|pdf)$", re.I)
    links: dict[str, str] = {}
    for href, title in parser.links:
        item_url = urljoin(issue_url, href)
        path = urlparse(item_url)
        if path.hostname != "www.resmigazete.gov.tr" or not pattern.search(path.path):
            continue
        key = _title_key(title)
        if key and key in links and links[key] != item_url:
            raise CollectionError(f"{issue_url}: ambiguous duplicate item title: {title}")
        if key:
            links[key] = item_url
    if not links:
        raise CollectionError(f"{issue_url}: no item links found")
    return links


def _decode_html(raw: bytes, charset: str | None, url: str) -> str:
    if charset is None:
        match = re.search(br"charset\s*=\s*['\"]?([\w-]+)", raw[:8192], re.I)
        charset = match.group(1).decode("ascii") if match else "utf-8"
    # Some official Word-generated HTML declares Windows-1254 while carrying UTF-8 bytes.
    candidates = ("utf-8", charset) if charset.lower() != "utf-8" else ("utf-8",)
    for candidate in candidates:
        try:
            return raw.decode(candidate)
        except (LookupError, UnicodeDecodeError):
            continue
    raise CollectionError(f"{url}: cannot decode HTML as UTF-8 or {charset}")


def extract_document_text(raw: bytes, media_type: str, charset: str | None, url: str) -> str:
    if urlparse(url).path.lower().endswith(".pdf") or "pdf" in media_type.lower():
        if not raw.startswith(b"%PDF-"):
            raise CollectionError(f"{url}: PDF URL returned non-PDF content")
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise CollectionError(f"{url}: PDF extraction failed: {exc}") from exc
    else:
        if media_type != "text/html":
            raise CollectionError(f"{url}: expected HTML, received {media_type}")
        parser = _BodyText()
        parser.feed(_decode_html(raw, charset, url))
        text = "".join(parser.parts)
    text = unicodedata.normalize("NFC", text).replace("\u00ad", "")
    text = "\n".join(" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in text.splitlines() if line).strip()


def retrieve_document(record: dict[str, Any], client: HtmlGetter) -> tuple[bytes, str]:
    url = record.get("document_url")
    if not url:
        raise CollectionError(f"{record['source_record_id']}: document URL unresolved")
    raw, media_type, charset = client.get(url, {"User-Agent": HEADERS["User-Agent"]})
    text = extract_document_text(raw, media_type, charset, url)
    record["raw_sha256"] = sha256_bytes(raw)
    record["normalized_sha256"] = sha256_bytes(text.encode("utf-8")) if text else None
    record["content_status"] = "text_extracted" if text else "text_unavailable"
    return raw, text


def resolve_document_urls(records: list[dict[str, Any]], client: HtmlGetter, day: date) -> dict[str, bytes]:
    """Match JSON index rows to links actually published by each issue fihrist."""
    raw_fihrists: dict[str, bytes] = {}
    lookup: dict[str, dict[str, str]] = {}
    for issue_url in dict.fromkeys(record["issue_url"] for record in records):
        raw, media_type, charset = client.get(issue_url, {"User-Agent": HEADERS["User-Agent"]})
        if media_type != "text/html":
            raise CollectionError(f"{issue_url}: expected fihrist HTML, received {media_type}")
        raw_fihrists[issue_url] = raw
        lookup[issue_url] = parse_fihrist_links(raw, day=day, issue_url=issue_url, charset=charset)
    for record in records:
        item_url = lookup[record["issue_url"]].get(_title_key(record["title"]))
        if not item_url:
            record["content_status"] = "link_unresolved"
            continue
        record["document_url"] = item_url
        record["content_status"] = "link_resolved"
    return raw_fihrists


def filter_payload(day: date, start: int) -> dict[str, Any]:
    return {
        "draw": start // PAGE_SIZE + 1,
        "start": start,
        "length": PAGE_SIZE,
        "columns": [],
        "order": [],
        "search": {"value": "", "regex": False},
        "parameters": {
            "searchtype": "1",
            "genelbaslangictarihi": day.isoformat(),
            "genelbitistarihi": day.isoformat(),
            "genelmukerrer": "",
        },
    }


def _required_string(row: dict[str, Any], name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str) or not value.strip():
        raise CollectionError(f"Resmî Gazete row missing {name}")
    return value.strip()


def normalize_row(row: dict[str, Any], requested_day: date) -> dict[str, Any]:
    title = _required_string(row, "konu")
    issue_value = row.get("resmiGazeteSayisi")
    if not isinstance(issue_value, (str, int)) or not str(issue_value).strip():
        raise CollectionError("Resmî Gazete row missing resmiGazeteSayisi")
    issue = str(issue_value).strip()
    published = _required_string(row, "resmiGazeteTarihi")[:10]
    if published != requested_day.isoformat():
        raise CollectionError(f"Resmî Gazete returned {published} for {requested_day}")
    issue_path = _required_string(row, "url")
    issue_url = urljoin(BASE_URL, issue_path)
    if urlparse(issue_url).hostname != "www.resmigazete.gov.tr":
        raise CollectionError(f"unexpected Resmî Gazete URL: {issue_url}")
    document_type = (row.get("mevzuatAdi") or "").strip()
    law_or_decision_no = str(row.get("kanunKararNo") or "").strip()
    duplicate_number = str(row.get("mukerrerSayisi") or "").strip()
    is_duplicate_issue = str(row.get("mukerrer") or "").upper() == "EVET"
    identity = [published, issue, duplicate_number, document_type, law_or_decision_no, title]
    record_id = "rg:" + hashlib.sha256(canonical_json(identity)).hexdigest()
    return {
        "source": "resmi_gazete",
        "source_record_id": record_id,
        "title": title,
        "document_type": document_type,
        "law_or_decision_number": law_or_decision_no or None,
        "source_published_at": published,
        "issue_number": issue,
        "is_duplicate_issue": is_duplicate_issue,
        "duplicate_issue_number": duplicate_number or None,
        "issue_url": issue_url,
        "document_url": None,
        "content_status": "discovered",
    }


def collect_index(day: date, client: JsonPoster) -> tuple[list[dict[str, Any]], list[bytes]]:
    """Return validated metadata and untouched response pages; never silently truncate."""
    rows: list[dict[str, Any]] = []
    raw_pages: list[bytes] = []
    expected_total: int | None = None
    start = 0
    while True:
        raw = client.post_json(FILTER_URL, filter_payload(day, start), HEADERS)
        body = parse_json_object(raw, FILTER_URL)
        data = body.get("data")
        total = body.get("recordsFiltered")
        if not isinstance(data, list) or not isinstance(total, int) or total < 0:
            raise CollectionError("Resmî Gazete filter response lacks data/recordsFiltered")
        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise CollectionError("Resmî Gazete result count changed during pagination")
        if len(data) > PAGE_SIZE or len(data) > total - start:
            raise CollectionError("Resmî Gazete pagination returned an impossible page")
        if total > start and not data:
            raise CollectionError("Resmî Gazete pagination stopped before all rows arrived")
        raw_pages.append(raw)
        rows.extend(data)
        if len(rows) >= total:
            break
        start += len(data)
    if len(rows) != expected_total:
        raise CollectionError("Resmî Gazete result count mismatch")
    normalized = [normalize_row(row, day) for row in rows]
    ids = [row["source_record_id"] for row in normalized]
    if len(ids) != len(set(ids)):
        raise CollectionError("Resmî Gazete returned colliding record identities")
    return normalized, raw_pages


def build_index_artifact(day: date, records: list[dict[str, Any]], raw_pages: list[bytes]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source": "resmi_gazete",
        "requested_date": day.isoformat(),
        "retrieved_at": utc_now(),
        "record_count": len(records),
        "link_resolved_count": sum(record["document_url"] is not None for record in records),
        "link_unresolved_count": sum(record["content_status"] == "link_unresolved" for record in records),
        "text_extracted_count": sum(record["content_status"] == "text_extracted" for record in records),
        "response_sha256": [sha256_bytes(page) for page in raw_pages],
        "records": records,
    }
