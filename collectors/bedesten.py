"""Focused consolidated-law retrieval from the public UYAP/Bedesten portal API."""

from __future__ import annotations

import base64
from typing import Any, Protocol

from collectors.common import CollectionError, parse_json_object, sha256_bytes, utc_now
from collectors.resmi_gazete import extract_document_text

BASE_URL = "https://bedesten.adalet.gov.tr/mevzuat"
PUBLIC_URL = "https://mevzuat.adalet.gov.tr/mevzuat/"
HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
    "Accept": "application/json",
    "AdaletApplicationName": "UyapMevzuat",
    "Origin": "https://mevzuat.adalet.gov.tr",
    "Referer": "https://mevzuat.adalet.gov.tr/",
    "User-Agent": "ISO-Pulse/0.1 (official-law collector)",
}


class JsonPoster(Protocol):
    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> bytes: ...


def _post(client: JsonPoster, endpoint: str, data: dict[str, Any], *, paging: bool = False) -> tuple[dict[str, Any], bytes]:
    payload: dict[str, Any] = {"data": data, "applicationName": "UyapMevzuat"}
    if paging:
        payload["paging"] = True
    url = BASE_URL + endpoint
    raw = client.post_json(url, payload, HEADERS)
    body = parse_json_object(raw, url)
    metadata = body.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("FMTY") != "SUCCESS":
        raise CollectionError(f"{url}: unsuccessful API response")
    return body, raw


def search_law(law_number: str, client: JsonPoster) -> tuple[dict[str, Any], bytes]:
    if not law_number.isdigit():
        raise ValueError("law number must contain only digits")
    body, raw = _post(client, "/searchDocuments", {
        "pageSize": 20,
        "pageNumber": 1,
        "sortFields": ["RESMI_GAZETE_TARIHI"],
        "sortDirection": "desc",
        "mevzuatTurList": ["KANUN"],
        "mevzuatNo": law_number,
    }, paging=True)
    data = body.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("mevzuatList"), list):
        raise CollectionError("Bedesten catalog response has no mevzuatList")
    matches = [row for row in data["mevzuatList"] if str(row.get("mevzuatNo") or "") == law_number]
    if len(matches) != 1 or data.get("total") != 1:
        raise CollectionError(f"Bedesten law {law_number}: expected one exact KANUN record, got {len(matches)}")
    row = matches[0]
    if not str(row.get("mevzuatId") or "").isdigit() or not str(row.get("mevzuatAdi") or "").strip():
        raise CollectionError(f"Bedesten law {law_number}: missing official id/title")
    return row, raw


def fetch_law(row: dict[str, Any], client: JsonPoster) -> tuple[dict[str, Any], bytes, bytes, str]:
    source_id = str(row["mevzuatId"])
    body, raw_response = _post(client, "/getDocumentContent", {
        "documentType": "MEVZUAT",
        "id": source_id,
    })
    data = body.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("content"), str) or not data["content"]:
        raise CollectionError(f"Bedesten {source_id}: empty or malformed content")
    mime_type = str(data.get("mimeType") or "").lower()
    if mime_type not in {"text/html", "text/plain", "application/pdf"}:
        raise CollectionError(f"Bedesten {source_id}: unsupported MIME type {mime_type}")
    encoded = data["content"]
    try:
        source_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise CollectionError(f"Bedesten {source_id}: invalid base64 content") from exc
    if not source_bytes:
        raise CollectionError(f"Bedesten {source_id}: decoded content is empty")
    if mime_type == "text/plain":
        try:
            text = source_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CollectionError(f"Bedesten {source_id}: invalid UTF-8 text") from exc
    else:
        text = extract_document_text(source_bytes, mime_type, None, PUBLIC_URL + source_id)
    if len(text) < 80:
        raise CollectionError(f"Bedesten {source_id}: extracted law text is unexpectedly short")
    record = {
        "schema_version": 1,
        "source": "bedesten",
        "source_record_id": source_id,
        "law_number": str(row["mevzuatNo"]),
        "title": str(row["mevzuatAdi"]).strip(),
        "source_type": "KANUN",
        "canonical_url": PUBLIC_URL + source_id,
        "catalog_url": BASE_URL + "/searchDocuments",
        "content_url": BASE_URL + "/getDocumentContent",
        "mime_type": mime_type,
        "source_version": data.get("version"),
        "raw_sha256": sha256_bytes(source_bytes),
        "normalized_sha256": sha256_bytes(text.encode("utf-8")),
        "retrieved_at": utc_now(),
        "normalizer_version": "bedesten-html-v1",
    }
    return record, raw_response, source_bytes, text
