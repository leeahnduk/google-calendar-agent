from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional


def parse_iso(dt: str) -> datetime:
    """Parse ISO-8601, tolerate 'Z'. Return timezone-aware UTC datetime."""
    return datetime.fromisoformat(dt.replace("Z", "+00:00")).astimezone(timezone.utc)


def should_generate(event_start_iso: str, lead_minutes: int, now: Optional[datetime] = None) -> bool:
    """
    Returns True if we are within the trigger window [start - lead, start) for generating the brief.
    """
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = parse_iso(event_start_iso)
    window_start = start - timedelta(minutes=lead_minutes)
    return window_start <= now_utc < start


def next_check_after(event_start_iso: str, lead_minutes: int, now: Optional[datetime] = None) -> datetime:
    """
    Compute the next time the scheduler should check again, to avoid excessive polling.
    If we are before window_start, return window_start. If inside window, return now + 1 minute.
    If event already started, return now.
    """
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = parse_iso(event_start_iso)
    window_start = start - timedelta(minutes=lead_minutes)
    if now_utc < window_start:
        return window_start
    if now_utc < start:
        return now_utc + timedelta(minutes=1)
    return now_utc
