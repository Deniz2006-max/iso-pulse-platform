#!/usr/bin/env python3
"""Discover one day's Resmî Gazete records and retain the source responses."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from collectors.common import CollectionError, HttpClient, atomic_write, canonical_json, fetch_pinned_intermediate, sha256_bytes
from collectors.versioning import compare_publications
from collectors.resmi_gazete import (
    INTERMEDIATE_DER_SHA256,
    INTERMEDIATE_URL,
    build_index_artifact,
    collect_index,
    retrieve_document,
    resolve_document_urls,
)


def run_collection(day: date, output: Path, client_factory: Callable[[], HttpClient]) -> tuple[int, dict]:
    """Retain every attempt; publish the latest index only after a complete run."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
    day_dir = output / "resmi_gazete" / day.isoformat()
    run_dir = day_dir / "runs" / run_id
    records: list[dict] = []
    raw_pages: list[bytes] = []
    client = None
    stage = "bootstrap"
    error = None
    comparison = None
    previous_index_sha256 = None
    try:
        stage = "previous_index"
        latest_path = day_dir / "index.json"
        if latest_path.exists():
            previous_raw = latest_path.read_bytes()
            previous = json.loads(previous_raw)
            if not isinstance(previous, dict) or previous.get("source") != "resmi_gazete" or previous.get("requested_date") != day.isoformat():
                raise CollectionError(f"invalid previous Gazette index: {latest_path}")
            previous_index_sha256 = sha256_bytes(previous_raw)
        else:
            previous = None
        stage = "bootstrap"
        client = client_factory()
        stage = "filter"
        records, raw_pages = collect_index(
            day, client, on_page=lambda number, raw: atomic_write(run_dir / f"filter-page-{number:03}.json", raw))
        stage = "fihrist"
        resolve_document_urls(
            records, client, day,
            on_fihrist=lambda number, raw: atomic_write(run_dir / f"fihrist-{number:03}.html", raw))
        stage = "document"
        for record in records:
            if not record["document_url"]:
                continue
            raw, text = retrieve_document(record, client)
            base = run_dir / "documents" / (
                record["source_record_id"].removeprefix("rg:") + "-" + record["raw_sha256"][:16]
            )
            suffix = ".pdf" if record["document_url"].lower().endswith(".pdf") else ".html"
            atomic_write(base.with_suffix(suffix), raw)
            record["raw_path"] = str((base.with_suffix(suffix)).relative_to(day_dir)).replace("\\", "/")
            if text:
                atomic_write(base.with_suffix(".txt"), text.encode("utf-8") + b"\n")
                record["text_path"] = str((base.with_suffix(".txt")).relative_to(day_dir)).replace("\\", "/")
        unavailable = sum(record["content_status"] != "text_extracted" for record in records)
        if unavailable:
            error = {"type": "IncompleteCollection", "message": f"{unavailable} records lack extracted text"}
        else:
            stage = "compare"
            comparison = compare_publications(previous, records)
            comparison["previous_index_sha256"] = previous_index_sha256
            comparison["requested_date"] = day.isoformat()
            artifact = build_index_artifact(day, records, raw_pages)
            artifact["comparison_path"] = f"runs/{run_id}/comparison.json"
            artifact["previous_index_sha256"] = previous_index_sha256
            atomic_write(run_dir / "comparison.json", canonical_json(comparison) + b"\n")
            atomic_write(run_dir / "index.json", canonical_json(artifact) + b"\n")
            stage = "publish"
            atomic_write(day_dir / "index.json", canonical_json(artifact) + b"\n")
    except (CollectionError, OSError, ValueError) as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        if records:
            atomic_write(run_dir / "partial-index.json", canonical_json(build_index_artifact(day, records, raw_pages)) + b"\n")
    manifest = {
        "schema_version": 1, "source": "resmi_gazete", "date": day.isoformat(), "run_id": run_id,
        "status": "complete" if error is None else "failed", "last_stage": stage,
        "record_count": len(records), "error": error,
        "request_log_path": f"runs/{run_id}/request-log.json",
        "comparison_path": f"runs/{run_id}/comparison.json" if comparison else None,
    }
    atomic_write(run_dir / "request-log.json", canonical_json(getattr(client, "request_log", [])) + b"\n")
    atomic_write(run_dir / "manifest.json", canonical_json(manifest) + b"\n")
    return (0 if error is None else 1), {"date": day.isoformat(), "records": len(records),
        "unresolved_links": sum(record.get("content_status") == "link_unresolved" for record in records),
        "unavailable_texts": sum(record.get("content_status") != "text_extracted" for record in records),
        "status": manifest["status"], "stage": stage, "error": error,
        "change_counts": comparison["counts"] if comparison else None,
        "missing_prior_publications": len(comparison["missing_prior_publication_ids"]) if comparison else None,
        "run": str(run_dir), "latest_index": str(day_dir / "index.json") if error is None else None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="Publication date: YYYY-MM-DD")
    parser.add_argument("--output", type=Path, default=Path("var/collectors"))
    parser.add_argument("--ca-bundle", help="PEM bundle containing any missing server intermediate CA")
    args = parser.parse_args()
    def make_client() -> HttpClient:
        extra_ca_pem = None if args.ca_bundle else fetch_pinned_intermediate(
            INTERMEDIATE_URL, INTERMEDIATE_DER_SHA256)
        return HttpClient(ca_bundle=args.ca_bundle, extra_ca_pem=extra_ca_pem)
    try:
        code, result = run_collection(args.date, args.output, make_client)
    except OSError as exc:
        print(f"cannot write collection run: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
