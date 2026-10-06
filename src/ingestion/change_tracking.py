"""Content-based change tracking for captured daily source records.

The tracker compares only records observed in the current collection run. A
missing record is never interpreted as a deletion because source coverage may
be partial (for example, SGK is currently sampled with a bounded page size).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from src.ingestion.models import DailyUpdate

STATE_SCHEMA_VERSION = 1


def _canonical_url(url: str) -> str:
    """Normalize harmless URL variation without dropping query parameters."""
    parts = urlsplit(url.strip())
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or "/",
            parts.query,
            "",
        )
    )


def stable_item_id(item: DailyUpdate) -> str:
    """Return a stable, source-scoped identifier for a collected item."""
    if item.url.strip():
        identity = _canonical_url(item.url)
    else:
        identity = "|".join(
            (
                item.publication_date.strip(),
                re.sub(r"\s+", " ", unicodedata.normalize("NFC", item.title)).strip().casefold(),
            )
        )
    digest = hashlib.sha256(f"{item.source}|{identity}".encode("utf-8")).hexdigest()
    return f"{item.source}:{digest}"


def content_sha256(item: DailyUpdate) -> str | None:
    """Hash meaningful captured content; return None when text is unavailable."""
    text = unicodedata.normalize("NFC", item.raw_text or "")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None
    payload = {
        "category": re.sub(r"\s+", " ", unicodedata.normalize("NFC", item.category)).strip(),
        "raw_text": text,
        "title": re.sub(r"\s+", " ", unicodedata.normalize("NFC", item.title)).strip(),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": STATE_SCHEMA_VERSION, "items": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read change-tracking state at {path}") from exc
    if (
        not isinstance(state, dict)
        or state.get("schema_version") != STATE_SCHEMA_VERSION
        or not isinstance(state.get("items"), dict)
    ):
        raise ValueError(f"Unsupported or malformed change-tracking state at {path}")
    return state


def write_json_atomic(path: Path, payload: Any) -> None:
    """Write JSON beside its destination, then atomically replace the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def track_changes(
    items: list[DailyUpdate],
    *,
    state_path: Path,
    run_date: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Compare current records with the last nonempty extraction and persist it.

    Blank extracted text is reported as ``unverified`` and does not replace a
    previously nonempty snapshot. No extraction-completeness or legal verification
    is implied by a nonempty text or a matching hash. Re-running the same date with identical
    content preserves that date's original status, making daily output
    idempotent for the normal scheduled rerun case.
    """
    try:
        datetime.strptime(run_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"run_date must be YYYY-MM-DD, got {run_date!r}") from exc

    state = _read_state(state_path)
    snapshots: dict[str, dict[str, Any]] = state["items"]
    observed: list[dict[str, Any]] = []
    counts = {"new": 0, "changed": 0, "unchanged": 0, "unverified": 0}
    now = generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    for item in items:
        item_id = stable_item_id(item)
        current_hash = content_sha256(item)
        previous = snapshots.get(item_id)
        previous_hash = previous.get("content_sha256") if previous else None

        if current_hash is None:
            status = "unverified"
        elif previous_hash is None:
            status = "new"
        elif current_hash == previous_hash:
            status = "unchanged"
        else:
            status = "changed"

        # Preserve the first result when the same daily capture is run again.
        reported_previous_hash = previous_hash
        if (
            previous
            and previous.get("last_seen_date") == run_date
            and previous.get("last_status") != "unverified"
            and current_hash is not None
            and current_hash == previous_hash
        ):
            status = previous.get("last_status", status)
            reported_previous_hash = previous.get(
                "last_previous_content_sha256", previous_hash
            )

        counts[status] += 1
        row = item.model_dump(mode="json")
        observed.append(
            {
                **row,
                "item_id": item_id,
                "change_status": status,
                "content_sha256": current_hash,
                "previous_content_sha256": reported_previous_hash,
            }
        )

        snapshot = dict(previous or {})
        snapshot.update(
            {
                "source": item.source,
                "url": item.url,
                "title": item.title,
                "first_seen_at": snapshot.get("first_seen_at", now),
                "last_seen_at": now,
                "last_seen_date": run_date,
                "last_status": status,
                "last_previous_content_sha256": reported_previous_hash,
            }
        )
        if current_hash is not None:
            snapshot["content_sha256"] = current_hash
        snapshots[item_id] = snapshot

    state["schema_version"] = STATE_SCHEMA_VERSION
    write_json_atomic(state_path, state)

    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "run_date": run_date,
        "generated_at": now,
        "comparison": "SHA-256 of normalized title, category, and extracted text",
        "missing_items_are_deletions": False,
        "counts": counts,
        "items": observed,
    }
