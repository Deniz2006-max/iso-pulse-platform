"""Calendar-day window for daily RG / SGK ingestion.

Keep only publications whose timestamp is on the selected calendar day,
starting at local midnight (00:00). Date-only values (YYYY-MM-DD) are
treated as 00:00 that morning.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, time
from typing import Iterable

from src.ingestion.models import DailyUpdate

LOGGER = logging.getLogger("iso_pulse.ingestion.day_window")

_ISO_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def local_midnight(day: date) -> datetime:
    """Start of the local calendar day (00:00)."""
    return datetime.combine(day, time.min)


def parse_publication_timestamp(value: str | None) -> datetime | None:
    """Parse a scraper date/datetime. Naive values are local time."""
    raw = (value or "").strip()
    if not raw:
        return None
    match = _ISO_DATE.match(raw)
    if match:
        try:
            day = date.fromisoformat(match.group(1))
        except ValueError:
            return None
        rest = raw[10:].lstrip("T ")
        if not rest:
            return datetime.combine(day, time.min)
        clock = rest[:8]
        try:
            parsed_time = datetime.strptime(clock, "%H:%M:%S").time()
        except ValueError:
            try:
                parsed_time = datetime.strptime(clock[:5], "%H:%M").time()
            except ValueError:
                parsed_time = time.min
        return datetime.combine(day, parsed_time)
    try:
        return datetime.combine(date.fromisoformat(raw[:10]), time.min)
    except ValueError:
        pass
    for fmt in ("%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw[:10], fmt)
        except ValueError:
            continue
    return None


def is_on_or_after_midnight(value: str | None, day: date) -> bool:
    """True when the publication is on `day` and at/after 00:00 local time."""
    stamp = parse_publication_timestamp(value)
    if stamp is None:
        return False
    start = local_midnight(day)
    end = datetime.combine(day, time.max)
    return start <= stamp <= end


def filter_published_today(
    items: Iterable[DailyUpdate],
    day: date,
) -> list[DailyUpdate]:
    """Drop rows published before 00:00 of `day` or on another calendar date."""
    kept: list[DailyUpdate] = []
    skipped = 0
    for item in items:
        if is_on_or_after_midnight(item.publication_date, day):
            kept.append(item)
        else:
            skipped += 1
            LOGGER.debug(
                "Skip off-window %s %s (%s)",
                item.source,
                item.publication_date,
                (item.title or "")[:60],
            )
    if skipped:
        LOGGER.info(
            "Midnight window %s 00:00+: kept %s, skipped %s older/other-day item(s)",
            day.isoformat(),
            len(kept),
            skipped,
        )
    return kept
