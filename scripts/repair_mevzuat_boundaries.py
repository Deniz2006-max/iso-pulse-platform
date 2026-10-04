"""Losslessly repair retained article boundaries in the seven main-branch JSONs.

The original PDFs are not in this repository. This migration only redistributes
text already present in the JSON; it cannot certify the source PDF or its date.
Run without --write for an audit summary, then use --write after review.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pdf_to_madde_json import (
    maddelere_ayir,
    sha256_kisa,
    sonraki_madde_basligini_ayir,
)

LETTERED = {"6331": ("24/A", "25/A"), "4632": ("20/A",)}


def _compact(text: str) -> str:
    return " ".join(text.split())


def _ordered_text(records: list[dict]) -> str:
    return _compact(" ".join(
        part for row in records for part in (row.get("heading", ""), row["text"])
        if part
    ))


def repair(payload: dict) -> tuple[dict, dict]:
    updated = copy.deepcopy(payload)
    document = updated["documents"][0]
    law_number = document["document_id"].split(":", 1)[1]
    original_records = payload["documents"][0]["included_provisions"]
    old_records = document["included_provisions"]
    for row in old_records:
        if row["normalized_hash"] != sha256_kisa(row["text"]):
            raise ValueError(f"stored hash mismatch: {row['provision_id']}")

    records: list[dict] = []
    split_ids: list[str] = []
    wanted = {f"law:{law_number}:article:{number}" for number in LETTERED.get(law_number, ())}
    existing_old_ids = {row["provision_id"] for row in old_records}
    for row in old_records:
        parent_targets = [number for number in LETTERED.get(law_number, ())
                          if row["provision_id"] == f"law:{law_number}:article:{number.split('/')[0]}"
                          and f"law:{law_number}:article:{number}" not in existing_old_ids]
        if not parent_targets:
            records.append(row)
            continue
        parts = maddelere_ayir(row["text"])
        if len(parts) != 2 or parts[1]["madde_no"] != parent_targets[0]:
            raise ValueError(f"unexpected lettered boundary: {row['provision_id']}")
        parent = row
        parent["text"] = parts[0]["govde"]
        parent["mulga"] = parts[0]["mulga"]
        child = {**row, "provision_id": f"law:{law_number}:article:{parts[1]['madde_no']}",
                 "label": f"Madde {parts[1]['madde_no']}",
                 "text": parts[1]["govde"], "mulga": parts[1]["mulga"]}
        if parts[1]["heading"]:
            child["heading"] = parts[1]["heading"]
        records.extend((parent, child))
        split_ids.append(child["provision_id"])
    existing = {row["provision_id"] for row in records}
    if set(split_ids) | (wanted & existing) != wanted:
        raise ValueError(f"expected lettered articles {wanted}, found {set(split_ids) | (wanted & existing)}")

    heading_moves = []
    for position, row in enumerate(records[:-1]):
        following = records[position + 1]
        if following.get("heading"):
            # Already migrated; never guess that another tail is also a heading.
            continue
        body, heading = sonraki_madde_basligini_ayir(row["text"])
        if heading:
            row["text"] = body
            following["heading"] = heading
            heading_moves.append({"from": row["provision_id"],
                                  "to": following["provision_id"], "heading": heading})
    for row in records:
        row["normalized_hash"] = sha256_kisa(row["text"])
    if len({row["provision_id"] for row in records}) != len(records):
        raise ValueError("duplicate provision ID after repair")
    if _ordered_text(original_records) != _ordered_text(records):
        raise ValueError(f"text loss or reordering in {law_number}")
    document["included_provisions"] = records
    return updated, {"document_id": document["document_id"],
                     "lettered_articles_added": split_ids, "headings_moved": len(heading_moves),
                     "heading_moves": heading_moves,
                     "provisions": len(records), "text_preserved": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "data" / "mevzuat")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--show-headings", action="store_true")
    args = parser.parse_args()
    for path in sorted(args.directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        updated, audit = repair(payload)
        summary = {"file": path.name, **audit}
        if not args.show_headings:
            summary.pop("heading_moves")
        print(json.dumps(summary, ensure_ascii=False))
        if args.write and updated != payload:
            path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
