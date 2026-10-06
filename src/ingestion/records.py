"""Shared helpers for daily pipeline records and Streamlit display."""

from __future__ import annotations

from typing import Any, Iterable

STALE_DEMO_DAYS = ("2026-10-01", "2026-10-05", "2026-10-06")


def _truthy_relevant(value: Any) -> bool:
    return value in (True, 1, "1", "true", "True")


def has_executive_card(row: dict[str, Any]) -> bool:
    delivery = row.get("delivery") if isinstance(row.get("delivery"), dict) else {}
    analyses = row.get("analyses") if isinstance(row.get("analyses"), dict) else {}
    departments = row.get("departments") or delivery.get("departments") or []
    summary = str(delivery.get("summary") or "").strip()
    return bool(summary or analyses or departments)


def is_passed_record(row: dict[str, Any]) -> bool:
    """True when the pre-filter kept the item for specialist / UI cards."""
    return _truthy_relevant(row.get("is_relevant"))


def passed_records(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if is_passed_record(row)]


def has_valid_cards(rows: Iterable[dict[str, Any]]) -> bool:
    return any(is_passed_record(row) for row in rows)


def metric_counts(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    """(examined, passed changes, passed cards with a unit mapping)."""
    passed = passed_records(rows)
    mapped = [
        row
        for row in passed
        if (
            row.get("departments")
            or (row.get("delivery") or {}).get("departments")
            or has_executive_card(row)
        )
    ]
    return len(rows), len(passed), len(mapped) if mapped else len(passed)
