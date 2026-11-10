"""Calendar-day arithmetic in America/Vancouver (R-03). The only date helpers in the product."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

CLINIC_TZ = ZoneInfo("America/Vancouver")


def local_today(now: datetime | None = None, tz: ZoneInfo = CLINIC_TZ) -> date:
    current = now if now is not None else datetime.now(tz=UTC)
    if current.tzinfo is None:
        raise ValueError("naive datetime")
    return current.astimezone(tz).date()


def local_date_of(ts: datetime, tz: ZoneInfo = CLINIC_TZ) -> date:
    if ts.tzinfo is None:
        raise ValueError("naive datetime")
    return ts.astimezone(tz).date()


def add_days(d: date, days: int) -> date:
    return d + timedelta(days=days)


def days_since(start: date, on: date) -> int:
    """Whole calendar days from start to on (same day = 0)."""
    return (on - start).days


def in_range(d: date, start: date, end: date | None) -> bool:
    """Inclusive range check; end None means open-ended."""
    return d >= start and (end is None or d <= end)
