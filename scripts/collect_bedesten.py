#!/usr/bin/env python3
"""Retrieve one current law as a local, content-addressed Bedesten baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from collectors.bedesten import fetch_law, search_law
from collectors.common import CollectionError, HttpClient, atomic_write, canonical_json


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
        old_hash = previous.get("normalized_sha256") if isinstance(previous, dict) else None
        changed = old_hash != record["normalized_sha256"]
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
        atomic_write(latest_path, canonical_json({**record, "version_path": str(version_dir.relative_to(law_dir)).replace("\\", "/")}) + b"\n")
    except (CollectionError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"collection failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"law_number": args.law_number, "source_mevzuat_id": record["source_record_id"], "changed": changed, "old_sha256": old_hash, "new_sha256": record["normalized_sha256"], "output": str(version_dir)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
