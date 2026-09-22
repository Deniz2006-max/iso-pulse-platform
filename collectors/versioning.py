"""Conservative, source-evidence-only version comparisons."""

from __future__ import annotations

import hashlib
from typing import Any

from collectors.common import CollectionError, canonical_json
from collectors.resmi_gazete import _decision_numbers


def classify_version(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    if previous is None:
        return "new"
    if previous.get("normalized_sha256") != current.get("normalized_sha256"):
        if previous.get("raw_sha256") == current.get("raw_sha256"):
            return "extraction_changed"
        if previous.get("normalizer_version") and current.get("normalizer_version") and previous.get("normalizer_version") != current.get("normalizer_version"):
            return "normalizer_changed"
        return "text_changed"
    if previous.get("raw_sha256") != current.get("raw_sha256"):
        return "raw_changed_only"
    if previous.get("title") != current.get("title") or previous.get("document_url") != current.get("document_url"):
        return "metadata_changed_only"
    return "unchanged"


def compare_law(previous: dict[str, Any] | None, current: dict[str, Any]) -> str:
    if previous is None:
        return "new"
    if previous.get("law_number") != current.get("law_number"):
        raise CollectionError("previous Bedesten snapshot belongs to a different law")
    if previous.get("source_record_id") != current.get("source_record_id"):
        return "source_id_changed"
    status = classify_version(previous, current)
    if status == "unchanged" and previous.get("source_version") != current.get("source_version"):
        return "metadata_changed_only"
    return status


def publication_identity(record: dict[str, Any]) -> tuple[str, str]:
    """Use official decision number, otherwise the verified item URL—not a mutable title."""
    required = ("title", "source_published_at", "issue_number", "document_type")
    if any(not record.get(field) for field in required):
        raise CollectionError("Gazette publication lacks required identity fields")
    number = record.get("law_or_decision_number")
    if not number:
        numbers = _decision_numbers(record["title"])
        number = next(iter(numbers)) if len(numbers) == 1 else None
    if number:
        basis, value = "decision_number", str(number)
    elif record.get("document_url"):
        basis, value = "document_url", record["document_url"]
    else:
        raise CollectionError(f"cannot identify publication without number or URL: {record['title']}")
    key = [record["source_published_at"], record["issue_number"],
           record.get("duplicate_issue_number"), record["document_type"], basis, value]
    return "rgpub:" + hashlib.sha256(canonical_json(key)).hexdigest(), basis


def compare_publications(previous: dict[str, Any] | None, records: list[dict[str, Any]]) -> dict[str, Any]:
    old_by_id: dict[str, dict[str, Any]] = {}
    old_records = previous.get("records") if previous else []
    if not isinstance(old_records, list):
        raise CollectionError("previous Gazette index has no records list")
    for old in old_records:
        if not isinstance(old, dict) or not old.get("raw_sha256") or not old.get("normalized_sha256"):
            raise CollectionError("previous Gazette index has a record without source hashes")
        old_id, _ = publication_identity(old)
        if old_id in old_by_id:
            raise CollectionError(f"previous Gazette index has duplicate publication identity: {old_id}")
        old_by_id[old_id] = old
    current_ids: set[str] = set()
    changes: list[dict[str, Any]] = []
    counts = {name: 0 for name in ("new", "text_changed", "raw_changed_only", "extraction_changed", "normalizer_changed", "metadata_changed_only", "unchanged")}
    for record in records:
        publication_id, basis = publication_identity(record)
        if publication_id in current_ids:
            raise CollectionError(f"current Gazette index has duplicate publication identity: {publication_id}")
        current_ids.add(publication_id)
        old = old_by_id.get(publication_id)
        status = classify_version(old, record)
        record["publication_id"] = publication_id
        record["identity_basis"] = basis
        record["change_status"] = status
        counts[status] += 1
        if status != "unchanged":
            changes.append({
                "publication_id": publication_id, "source_record_id": record["source_record_id"],
                "change_status": status, "title": record["title"], "document_url": record["document_url"],
                "old_title": old.get("title") if old else None,
                "old_document_url": old.get("document_url") if old else None,
                "old_raw_sha256": old.get("raw_sha256") if old else None,
                "new_raw_sha256": record["raw_sha256"],
                "old_normalized_sha256": old.get("normalized_sha256") if old else None,
                "new_normalized_sha256": record["normalized_sha256"],
                "old_raw_path": old.get("raw_path") if old else None,
                "new_raw_path": record["raw_path"],
                "old_text_path": old.get("text_path") if old else None,
                "new_text_path": record.get("text_path"),
            })
    return {"schema_version": 1, "source": "resmi_gazete", "counts": counts, "changes": changes,
            "missing_prior_publication_ids": sorted(old_by_id.keys() - current_ids)}
