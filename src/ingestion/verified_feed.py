"""Convert retained collector evidence into the app's existing DailyUpdate feed.

This is an input adapter, not a legal-effect analyser. It accepts complete
collector indexes, verifies the referenced source files, and keeps its audit
decisions in evidence.json. The app-facing JSON retains the unchanged schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.ingestion.models import DailyUpdate, SGK_BASELINE_DOCUMENT_IDS


class EvidenceError(ValueError):
    pass


NUMBERED_REFERENCE = re.compile(r"(?<!\d)(\d{3,5})\s+sayılı\b", re.IGNORECASE)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _artifact(root: Path, relative: str | None) -> Path:
    if not relative:
        raise EvidenceError("missing evidence path")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise EvidenceError(f"evidence path escapes collector directory: {relative}")
    if not target.is_file():
        raise EvidenceError(f"evidence file missing: {relative}")
    return target


def _verified_bytes(root: Path, relative: str | None, expected: str | None) -> bytes:
    if not expected or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise EvidenceError("missing or invalid source SHA-256")
    raw = _artifact(root, relative).read_bytes()
    if _sha256(raw) != expected:
        raise EvidenceError(f"source SHA-256 mismatch: {relative}")
    return raw


def _verified_text(root: Path, relative: str | None, expected: str | None) -> str:
    # Collector text files contain exactly one newline after the hashed text.
    raw = _artifact(root, relative).read_bytes()
    try:
        text = raw.decode("utf-8").removesuffix("\n")
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"source text is not UTF-8: {relative}") from exc
    if not expected or _sha256(text.encode("utf-8")) != expected:
        raise EvidenceError(f"text SHA-256 mismatch: {relative}")
    if len(text.strip()) < 100:
        raise EvidenceError(f"source text is too short for automatic handoff: {relative}")
    if any(ord(character) < 32 and character not in "\t\n\r" for character in text):
        raise EvidenceError(f"source text contains control characters: {relative}")
    return text


def _mentions(text: str) -> list[dict[str, Any]]:
    """Literal numbered mentions only; never infer amendment or legal effect."""
    found = []
    for match in NUMBERED_REFERENCE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        left = text.rfind("\n", 0, match.start()) + 1
        right = text.find("\n", match.end())
        if right < 0:
            right = len(text)
        found.append({"number": match.group(1), "line": line,
                      "excerpt": text[left:right][:300], "relation": "mention_only"})
    return found


def _load_index(path: Path, source: str) -> tuple[dict, str]:
    raw = path.read_bytes()
    index = json.loads(raw)
    if index.get("source") != source or not isinstance(index.get("records"), list):
        raise EvidenceError(f"invalid {source} collector index: {path}")
    return index, _sha256(raw)


def _rg(index_path: Path, day: date) -> tuple[list[DailyUpdate], list[dict], str]:
    index, index_hash = _load_index(index_path, "resmi_gazete")
    if index.get("requested_date") != day.isoformat():
        raise EvidenceError("Gazette index date differs from feed date")
    if index.get("record_count") != len(index["records"]):
        raise EvidenceError("Gazette index record count mismatch")
    root = index_path.parent
    counts = Counter(row.get("document_url") for row in index["records"])
    updates, audit = [], []
    for row in index["records"]:
        report = {"source": "resmi_gazete", "source_record_id": row.get("source_record_id"),
                  "publication_id": row.get("publication_id"), "source_url": row.get("document_url"),
                  "change_status": row.get("change_status"), "raw_path": row.get("raw_path"),
                  "text_path": row.get("text_path"), "raw_sha256": row.get("raw_sha256"),
                  "text_sha256": row.get("normalized_sha256")}
        try:
            if row.get("content_status") != "text_extracted":
                raise EvidenceError("collector did not extract complete text")
            if not row.get("document_url") or counts[row["document_url"]] != 1:
                raise EvidenceError("shared or missing source document; publication text not isolated")
            _verified_bytes(root, row.get("raw_path"), row.get("raw_sha256"))
            text = _verified_text(root, row.get("text_path"), row.get("normalized_sha256"))
            update = DailyUpdate(
                source="resmi_gazete", publication_date=row["source_published_at"],
                title=row["title"], category=row["document_type"],
                url=row["document_url"], raw_text=text,
                fetched_at=index["retrieved_at"],
            )
            report.update(status="included", literal_numbered_references=_mentions(text))
            updates.append(update)
        except (EvidenceError, KeyError, ValueError) as exc:
            report.update(status="held_for_review", reason=str(exc))
        audit.append(report)
    return updates, audit, index_hash


def _sgk(index_path: Path) -> tuple[list[DailyUpdate], list[dict], str]:
    index, index_hash = _load_index(index_path, "sgk")
    if index.get("record_count") != len(index["records"]) or not index.get("source_capture_complete"):
        raise EvidenceError("SGK page capture is incomplete")
    root = index_path.parent
    _verified_bytes(root, index.get("listing_raw_path"), index.get("listing_raw_sha256"))
    updates, audit = [], []
    for row in index["records"]:
        report = {"source": "sgk", "source_record_id": row.get("source_record_id"),
                  "source_url": row.get("canonical_url"), "change_status": row.get("change_status"),
                  "detail_raw_path": row.get("detail_raw_path"),
                  "detail_raw_sha256": row.get("detail_raw_sha256"), "attachments": []}
        try:
            _verified_bytes(root, row.get("detail_raw_path"), row.get("detail_raw_sha256"))
            body = row["body_text"]
            body_hash = _sha256(_canonical_json({
                "title": row["title"], "unit": row["publishing_unit"],
                "published_at": row["source_published_at"], "body": body,
            }))
            if body_hash != row.get("normalized_sha256"):
                raise EvidenceError("SGK detail/body hash mismatch")
            if any(ord(character) < 32 and character not in "\t\n\r" for character in body):
                raise EvidenceError("SGK detail/body contains control characters")
            parts = [body.strip()] if body.strip() else []
            for attachment in row.get("attachments", []):
                evidence = {"url": attachment.get("url"), "raw_path": attachment.get("raw_path"),
                            "text_path": attachment.get("text_path"),
                            "raw_sha256": attachment.get("raw_sha256"),
                            "text_sha256": attachment.get("normalized_sha256")}
                report["attachments"].append(evidence)
                _verified_bytes(root, attachment.get("raw_path"), attachment.get("raw_sha256"))
                if attachment.get("text_status") != "text_extracted":
                    raise EvidenceError(f"SGK attachment text incomplete: {attachment.get('url')}")
                text = _verified_text(root, attachment.get("text_path"), attachment.get("normalized_sha256"))
                parts.append(f"[Ek: {attachment['url']}]\n{text}")
            combined = "\n\n".join(parts)
            if len(combined.strip()) < 100:
                raise EvidenceError("SGK announcement text too short for automatic handoff")
            update = DailyUpdate(
                source="sgk", publication_date=row["source_published_at"],
                title=row["title"], category="Genelge" if "genelge" in row["title"].casefold() else "Duyuru",
                url=row["canonical_url"], raw_text=combined,
                fetched_at=index["collected_at"],
                baseline_document_ids=list(SGK_BASELINE_DOCUMENT_IDS),
            )
            report.update(status="included", literal_numbered_references=_mentions(combined))
            updates.append(update)
        except (EvidenceError, KeyError, ValueError) as exc:
            report.update(status="held_for_review", reason=str(exc))
        audit.append(report)
    return updates, audit, index_hash


def build_feed(rg_index: Path, sgk_index: Path, day: date) -> tuple[dict[str, list[dict]], dict]:
    rg, rg_audit, rg_hash = _rg(rg_index.resolve(), day)
    sgk, sgk_audit, sgk_hash = _sgk(sgk_index.resolve())
    if not rg and not sgk:
        raise EvidenceError("no verified records; refusing an apparently empty daily feed")
    payload = {"resmi_gazete.json": [row.model_dump() for row in rg],
               "sgk.json": [row.model_dump() for row in sgk],
               "all.json": [row.model_dump() for row in [*rg, *sgk]]}
    evidence = {"schema_version": 1, "stage": "source_integrity_handoff",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "legal_effect_verified": False, "content_completeness_verified": False,
                "automatic_legal_reporting_allowed": False,
                "source_indexes": [
                    {"path": str(rg_index.resolve()), "sha256": rg_hash},
                    {"path": str(sgk_index.resolve()), "sha256": sgk_hash},
                ], "records": [*rg_audit, *sgk_audit]}
    return payload, evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--resmi-gazete-index", type=Path, required=True)
    parser.add_argument("--sgk-index", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True,
                        help="New YYYY-MM-DD directory; existing directories are never overwritten")
    args = parser.parse_args()
    payload, evidence = build_feed(args.resmi_gazete_index, args.sgk_index, args.date)
    if args.output_directory.exists():
        raise SystemExit(f"output directory already exists: {args.output_directory}")
    args.output_directory.mkdir(parents=True)
    for name, rows in payload.items():
        (args.output_directory / name).write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_directory / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output_directory),
                      "included": len(payload["all.json"]),
                      "held_for_review": sum(row["status"] == "held_for_review"
                                             for row in evidence["records"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
