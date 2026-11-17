from __future__ import annotations

from datetime import UTC, date, datetime

from aria.agents.aria.receivables.models import Freshness, SourceRecord


def freshness(as_of: datetime, now: datetime, max_age_seconds: int) -> tuple[Freshness, int | None]:
    if as_of.tzinfo is None or now.tzinfo is None or max_age_seconds < 0:
        return Freshness.UNKNOWN, None
    delta = now.astimezone(UTC) - as_of.astimezone(UTC)
    if delta.total_seconds() < 0:
        return Freshness.UNKNOWN, int(delta.total_seconds())
    age = int(delta.total_seconds())
    return (Freshness.FRESH if age <= max_age_seconds else Freshness.STALE), age


def policy_is_effective(start: date, end: date, clock_date: date) -> bool:
    return start <= clock_date <= end


def proposal_is_current(created_at: datetime, expires_at: datetime, now: datetime) -> bool:
    return created_at <= now <= expires_at


def record_set_unchanged(
    expected: tuple[SourceRecord, ...], current: tuple[SourceRecord, ...]
) -> bool:
    return expected == current
