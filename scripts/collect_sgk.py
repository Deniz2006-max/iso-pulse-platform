#!/usr/bin/env python3
"""Capture one bounded SGK announcement listing page and its linked evidence."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from collectors.common import CollectionError, HttpClient, atomic_write, canonical_json, sha256_bytes, utc_now
from collectors.office_text import extract_office_text
from collectors.resmi_gazete import extract_document_text
from collectors.sgk import HEADERS, UNIT, compare_announcements, listing_url, parse_detail, parse_listing


def run_collection(page: int, output: Path, client_factory: Callable[[], HttpClient],
                   *, delay_seconds: float = 1.0) -> tuple[int, dict]:
    """A failed run retains evidence but never replaces the last complete page index."""
    if page < 1 or delay_seconds < 0:
        raise ValueError("page must be >= 1 and delay must be nonnegative")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    page_dir = output / "sgk" / UNIT / f"page-{page:03d}"
    run_dir = page_dir / "runs" / run_id
    records: list[dict] = []
    client = None
    stage = "previous_index"
    error = None
    comparison = None
    listing = listing_url(page)
    try:
        latest_path = page_dir / "index.json"
        if latest_path.exists():
            old_raw = latest_path.read_bytes()
            previous = json.loads(old_raw)
            if not isinstance(previous, dict) or previous.get("source") != "sgk" or previous.get("page") != page:
                raise CollectionError(f"invalid previous SGK page index: {latest_path}")
            previous_index_sha256 = sha256_bytes(old_raw)
        else:
            previous = None
            previous_index_sha256 = None
        client = client_factory()
        stage = "listing"
        raw_listing, media_type, charset = client.get(listing, HEADERS, stage=stage)
        atomic_write(run_dir / "listing.html", raw_listing)
        links = parse_listing(raw_listing, media_type, charset, listing)
        for position, url in enumerate(links, start=1):
            if delay_seconds:
                time.sleep(delay_seconds)
            stage = "detail"
            raw_detail, media_type, charset = client.get(url, HEADERS, stage=stage)
            relative_detail = Path("runs") / run_id / "details" / f"{position:03d}-{sha256_bytes(url.encode())[:12]}.html"
            atomic_write(page_dir / relative_detail, raw_detail)
            record = parse_detail(raw_detail, media_type, charset, url)
            record["listing_position"] = position
            record["detail_raw_path"] = relative_detail.as_posix()
            record["retrieved_at"] = utc_now()
            records.append(record)
            for attachment_number, attachment in enumerate(record["attachments"], start=1):
                if delay_seconds:
                    time.sleep(delay_seconds)
                stage = "attachment"
                raw_file, file_type, _ = client.get(attachment["url"], HEADERS, stage=stage)
                if not raw_file or file_type == "text/html":
                    raise CollectionError(f"{attachment['url']}: empty file or HTML fallback")
                base = Path("runs") / run_id / "attachments" / (
                    f"{position:03d}-{attachment_number:02d}-{sha256_bytes(attachment['url'].encode())[:12]}")
                relative_file = base.with_suffix("." + attachment["extension"])
                atomic_write(page_dir / relative_file, raw_file)
                attachment["raw_path"] = relative_file.as_posix()
                attachment["raw_sha256"] = sha256_bytes(raw_file)
                attachment["media_type"] = file_type
                if attachment["extension"] == "pdf":
                    stage = "pdf_extraction"
                    if not raw_file.startswith(b"%PDF-"):
                        raise CollectionError(f"{attachment['url']}: PDF link returned non-PDF bytes")
                    text = extract_document_text(raw_file, "application/pdf", None, attachment["url"])
                    if text:
                        relative_text = base.with_suffix(".txt")
                        atomic_write(page_dir / relative_text, text.encode("utf-8") + b"\n")
                        attachment["text_path"] = relative_text.as_posix()
                        attachment["normalized_sha256"] = sha256_bytes(text.encode("utf-8"))
                        attachment["text_status"] = "text_extracted"
                    else:
                        attachment["text_path"] = None
                        attachment["normalized_sha256"] = None
                        attachment["text_status"] = "needs_ocr"
                elif attachment["extension"] in {"docx", "xlsx"}:
                    stage = "office_extraction"
                    text, text_status = extract_office_text(raw_file, attachment["extension"])
                    if text:
                        relative_text = base.with_suffix(".txt")
                        atomic_write(page_dir / relative_text, text.encode("utf-8") + b"\n")
                        attachment["text_path"] = relative_text.as_posix()
                        attachment["normalized_sha256"] = sha256_bytes(text.encode("utf-8"))
                    else:
                        attachment["text_path"] = None
                        attachment["normalized_sha256"] = None
                    attachment["text_status"] = text_status
                else:
                    attachment["text_path"] = None
                    attachment["normalized_sha256"] = None
                    attachment["text_status"] = "binary_retained_unparsed"
            record["normalized_sha256"] = sha256_bytes(canonical_json({
                "title": record["title"], "unit": record["publishing_unit"],
                "published_at": record["source_published_at"], "body": record["body_text"]}))
            record["attachment_set_sha256"] = sha256_bytes(canonical_json(sorted(
                (item["url"], item["raw_sha256"])
                for item in record["attachments"])))
            record["attachment_text_set_sha256"] = sha256_bytes(canonical_json(sorted(
                (item["url"], item["normalized_sha256"])
                for item in record["attachments"])))
        stage = "compare"
        comparison = compare_announcements(previous, records)
        comparison["previous_index_sha256"] = previous_index_sha256
        text_gaps = sum(item["text_status"] != "text_extracted"
                        for record in records for item in record["attachments"])
        artifact = {"schema_version": 1, "source": "sgk", "unit_filter": UNIT, "page": page,
                    "listing_url": listing, "listing_raw_sha256": sha256_bytes(raw_listing),
                    "listing_raw_path": f"runs/{run_id}/listing.html", "run_id": run_id,
                    "collected_at": utc_now(), "record_count": len(records), "records": records,
                    "source_capture_complete": True, "attachment_text_gap_count": text_gaps,
                    "attachment_text_complete": text_gaps == 0,
                    "comparison_path": f"runs/{run_id}/comparison.json"}
        atomic_write(run_dir / "comparison.json", canonical_json(comparison) + b"\n")
        atomic_write(run_dir / "index.json", canonical_json(artifact) + b"\n")
        stage = "publish"
        atomic_write(page_dir / "index.json", canonical_json(artifact) + b"\n")
    except (CollectionError, OSError, ValueError, json.JSONDecodeError) as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        if records:
            atomic_write(run_dir / "partial-index.json", canonical_json({
                "source": "sgk", "page": page, "records": records}) + b"\n")
    manifest = {"schema_version": 1, "source": "sgk", "unit_filter": UNIT, "page": page,
                "run_id": run_id, "status": "complete" if error is None else "failed",
                "last_stage": stage, "record_count": len(records), "error": error,
                "attachment_text_complete": text_gaps == 0 if error is None else False,
                "request_log_path": f"runs/{run_id}/request-log.json",
                "comparison_path": f"runs/{run_id}/comparison.json" if comparison else None}
    atomic_write(run_dir / "request-log.json", canonical_json(getattr(client, "request_log", [])) + b"\n")
    atomic_write(run_dir / "manifest.json", canonical_json(manifest) + b"\n")
    return (0 if error is None else 1), {
        "status": manifest["status"], "stage": stage, "page": page, "records": len(records),
        "attachment_count": sum(len(item["attachments"]) for item in records),
        "binary_unparsed_count": sum(item.get("text_status") == "binary_retained_unparsed"
                                     for record in records for item in record["attachments"]),
        "partial_text_count": sum(item.get("text_status") == "partial_text_requires_review"
                                  for record in records for item in record["attachments"]),
        "needs_ocr_count": sum(item.get("text_status") == "needs_ocr"
                               for record in records for item in record["attachments"]),
        "attachment_text_complete": manifest["attachment_text_complete"],
        "change_counts": comparison["counts"] if comparison else None,
        "missing_prior_ids": len(comparison["missing_prior_ids"]) if comparison else None,
        "error": error, "run": str(run_dir),
        "latest_index": str(page_dir / "index.json") if error is None else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", type=int, default=1, help="One SGK TumBirimler page; default 1")
    parser.add_argument("--output", type=Path, default=Path("var/collectors"))
    parser.add_argument("--delay-seconds", type=float, default=1.0, help="Pause between official requests")
    args = parser.parse_args()
    try:
        code, result = run_collection(args.page, args.output, HttpClient, delay_seconds=args.delay_seconds)
    except (OSError, ValueError) as exc:
        print(f"cannot start SGK collection: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
