"""Tests for SessionClock — verify session windows, overlap, and liquidity scoring."""

from datetime import datetime, timezone

from core.sessions import Session, SessionClock


def _utc(hour: int) -> datetime:
    return datetime(2026, 6, 21, hour, 0, tzinfo=timezone.utc)


def test_asia_only_early_morning():
    state = SessionClock().state_at(_utc(1))  # 01:00 UTC
    assert Session.ASIA in state.active
    assert Session.LONDON not in state.active
    assert not state.is_overlap


def test_london_ny_overlap_is_peak():
    for hour in (13, 14, 15, 16):  # 13:00–17:00 UTC, end exclusive
        state = SessionClock().state_at(_utc(hour))
        assert state.is_overlap, f"hour {hour} should be overlap"
        assert state.liquidity_score == 1.0
        assert state.label == "london_ny_overlap"


def test_overlap_boundaries():
    # 12:00 is NY pre-open (London only); 17:00 London closes (NY only)
    assert not SessionClock().state_at(_utc(12)).is_overlap
    assert not SessionClock().state_at(_utc(17)).is_overlap


def test_low_liquidity_window():
    state = SessionClock().state_at(_utc(3))  # 03:00 UTC, low-liquidity
    assert state.is_low_liquidity
    assert state.liquidity_score == 0.2


def test_naive_datetime_assumed_utc():
    naive = datetime(2026, 6, 21, 14, 0)  # no tzinfo
    assert SessionClock().state_at(naive).is_overlap


def test_next_overlap_start_strictly_after():
    clock = SessionClock()
    before = _utc(10)
    nxt = clock.next_overlap_start(before)
    assert nxt.hour == 13 and nxt.date() == before.date()

    after = _utc(20)
    nxt2 = clock.next_overlap_start(after)
    assert nxt2.hour == 13 and nxt2.day == after.day + 1
