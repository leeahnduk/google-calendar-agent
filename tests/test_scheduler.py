from datetime import datetime, timedelta, timezone

from agents.scheduler import should_generate, next_check_after


def test_should_generate_inside_window():
    start = (datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)).isoformat()
    now = datetime(2025, 1, 1, 11, 40, 0, tzinfo=timezone.utc)
    assert should_generate(start, lead_minutes=30, now=now) is True


def test_should_generate_outside_window_before():
    start = (datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)).isoformat()
    now = datetime(2025, 1, 1, 11, 20, 0, tzinfo=timezone.utc)
    assert should_generate(start, lead_minutes=30, now=now) is False


def test_next_check_after_returns_window_start_if_before():
    start = (datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)).isoformat()
    now = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    nxt = next_check_after(start, lead_minutes=30, now=now)
    assert nxt == datetime(2025, 1, 1, 11, 30, 0, tzinfo=timezone.utc)
