#!/usr/bin/env python3
"""Discover one day's Resmî Gazete records and retain the source responses."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from collectors.common import CollectionError, HttpClient, atomic_write, canonical_json, fetch_pinned_intermediate
from collectors.resmi_gazete import (
    INTERMEDIATE_DER_SHA256,
    INTERMEDIATE_URL,
    build_index_artifact,
    collect_index,
    retrieve_document,
    resolve_document_urls,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="Publication date: YYYY-MM-DD")
    parser.add_argument("--output", type=Path, default=Path("var/collectors"))
    parser.add_argument("--ca-bundle", help="PEM bundle containing any missing server intermediate CA")
    args = parser.parse_args()
    try:
        extra_ca_pem = None if args.ca_bundle else fetch_pinned_intermediate(
            INTERMEDIATE_URL, INTERMEDIATE_DER_SHA256
        )
        client = HttpClient(ca_bundle=args.ca_bundle, extra_ca_pem=extra_ca_pem)
        records, raw_pages = collect_index(args.date, client)
        fihrists = resolve_document_urls(records, client, args.date)
        run_dir = args.output / "resmi_gazete" / args.date.isoformat()
        for number, raw in enumerate(raw_pages, start=1):
            atomic_write(run_dir / f"filter-page-{number:03}.json", raw)
        for number, raw in enumerate(fihrists.values(), start=1):
            atomic_write(run_dir / f"fihrist-{number:03}.html", raw)
        for record in records:
            if not record["document_url"]:
                continue
            raw, text = retrieve_document(record, client)
            base = run_dir / "documents" / (
                record["source_record_id"].removeprefix("rg:") + "-" + record["raw_sha256"][:16]
            )
            suffix = ".pdf" if record["document_url"].lower().endswith(".pdf") else ".html"
            atomic_write(base.with_suffix(suffix), raw)
            record["raw_path"] = str(base.with_suffix(suffix).relative_to(run_dir)).replace("\\", "/")
            if text:
                atomic_write(base.with_suffix(".txt"), text.encode("utf-8") + b"\n")
                record["text_path"] = str(base.with_suffix(".txt").relative_to(run_dir)).replace("\\", "/")
        artifact = build_index_artifact(args.date, records, raw_pages)
        atomic_write(run_dir / "index.json", canonical_json(artifact) + b"\n")
    except (CollectionError, OSError, ValueError) as exc:
        print(f"collection failed: {exc}", file=sys.stderr)
        return 1
    unresolved = artifact["link_unresolved_count"]
    unavailable = sum(record["content_status"] != "text_extracted" for record in records)
    print(json.dumps({"date": args.date.isoformat(), "records": len(records), "unresolved_links": unresolved, "unavailable_texts": unavailable, "output": str(run_dir)}, ensure_ascii=False))
    return 2 if unavailable else 0


if __name__ == "__main__":
    raise SystemExit(main())
