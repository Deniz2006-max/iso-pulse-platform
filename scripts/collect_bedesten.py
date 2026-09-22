#!/usr/bin/env python3
"""Retrieve one current law as a local, content-addressed Bedesten baseline."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from collectors.bedesten import fetch_law, search_law
from collectors.common import CollectionError, HttpClient, atomic_write, canonical_json
from collectors.versioning import compare_law


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--law-number", required=True)
    parser.add_argument("--output", type=Path, default=Path("var/collectors"))
    args = parser.parse_args()
    try:
        client = HttpClient()
        catalog_row, catalog_raw = search_law(args.law_number, client)
        record, content_raw, source_bytes, text = fetch_law(catalog_row, client)
        law_dir = args.output / "bedesten" / args.law_number
        latest_path = law_dir / "latest.json"
        previous = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() else None
        if previous is not None and not isinstance(previous, dict):
            raise CollectionError(f"invalid previous Bedesten snapshot: {latest_path}")
        status = compare_law(previous, record)
        old_hash = previous.get("normalized_sha256") if previous else None
        old_raw_hash = previous.get("raw_sha256") if previous else None
        changed = status != "unchanged"
        version_dir = law_dir / "versions" / record["normalized_sha256"] / record["raw_sha256"]
        suffix = ".pdf" if record["mime_type"] == "application/pdf" else ".html" if record["mime_type"] == "text/html" else ".txt"
        if not version_dir.exists():
            atomic_write(version_dir / "catalog-response.json", catalog_raw)
            atomic_write(version_dir / "content-response.json", content_raw)
            atomic_write(version_dir / ("source" + suffix), source_bytes)
            atomic_write(version_dir / "normalized.txt", text.encode("utf-8") + b"\n")
            atomic_write(version_dir / "metadata.json", canonical_json(record) + b"\n")
        else:
            required = ["catalog-response.json", "content-response.json", "source" + suffix, "normalized.txt", "metadata.json"]
            if any(not (version_dir / name).is_file() for name in required):
                raise CollectionError(f"incomplete existing version: {version_dir}")
        check_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid4().hex[:8]
        check_path = law_dir / "checks" / f"{check_id}.json"
        comparison = {
            "schema_version": 1, "source": "bedesten", "law_number": args.law_number,
            "change_status": status, "source_record_id": record["source_record_id"],
            "previous_source_record_id": previous.get("source_record_id") if previous else None,
            "old_raw_sha256": old_raw_hash, "new_raw_sha256": record["raw_sha256"],
            "old_normalized_sha256": old_hash, "new_normalized_sha256": record["normalized_sha256"],
            "previous_version_path": previous.get("version_path") if previous else None,
            "version_path": str(version_dir.relative_to(law_dir)).replace("\\", "/"),
        }
        atomic_write(check_path, canonical_json(comparison) + b"\n")
        atomic_write(latest_path, canonical_json({**record, "version_path": comparison["version_path"],
                                                 "last_check_path": str(check_path.relative_to(law_dir)).replace("\\", "/")}) + b"\n")
    except (CollectionError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"collection failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"law_number": args.law_number, "source_mevzuat_id": record["source_record_id"],
                      "change_status": status, "changed": changed, "old_sha256": old_hash,
                      "new_sha256": record["normalized_sha256"], "check": str(check_path),
                      "output": str(version_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
