"""SessionClock — maps a UTC timestamp to the active crypto trading session(s)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class Session(str, Enum):
    ASIA = "asia"
    LONDON = "london"
    NEW_YORK = "new_york"


# (start_hour, end_hour) in UTC, end exclusive.
_SESSION_WINDOWS: dict[Session, tuple[int, int]] = {
    Session.ASIA: (0, 9),
    Session.LONDON: (8, 17),
    Session.NEW_YORK: (13, 22),
}

_LOW_LIQUIDITY_WINDOWS: tuple[tuple[int, int], ...] = ((2, 6), (21, 23))


@dataclass(frozen=True)
class SessionState:
    """Snapshot of session context for a given instant."""

    ts: datetime
    active: tuple[Session, ...]
    is_overlap: bool          # London/NY overlap (13:00–17:00 UTC)
    is_low_liquidity: bool
    liquidity_score: float    # 0.0 (dead) → 1.0 (peak overlap)

    @property
    def label(self) -> str:
        if self.is_overlap:
            return "london_ny_overlap"
        if self.active:
            return "+".join(s.value for s in self.active)
        return "off_session"


def _to_utc(ts: datetime) -> datetime:
    """Normalize any datetime to timezone-aware UTC (assume naive == UTC)."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _in_window(hour: int, window: tuple[int, int]) -> bool:
    start, end = window
    return start <= hour < end


class SessionClock:
    """Stateless mapper from UTC time → SessionState."""

    def state_at(self, ts: datetime) -> SessionState:
        ts = _to_utc(ts)
        hour = ts.hour

        active = tuple(
            s for s, w in _SESSION_WINDOWS.items() if _in_window(hour, w)
        )
        is_overlap = Session.LONDON in active and Session.NEW_YORK in active
        is_low_liquidity = any(_in_window(hour, w) for w in _LOW_LIQUIDITY_WINDOWS)

        liquidity_score = self._liquidity_score(
            n_active=len(active), is_overlap=is_overlap, is_low_liquidity=is_low_liquidity
        )

        return SessionState(
            ts=ts,
            active=active,
            is_overlap=is_overlap,
            is_low_liquidity=is_low_liquidity,
            liquidity_score=liquidity_score,
        )

    def now(self) -> SessionState:
        return self.state_at(datetime.now(timezone.utc))

    @staticmethod
    def _liquidity_score(*, n_active: int, is_overlap: bool, is_low_liquidity: bool) -> float:
        if is_overlap:
            return 1.0
        if is_low_liquidity:
            return 0.2
        if n_active >= 2:
            return 0.8
        if n_active == 1:
            return 0.6
        return 0.4  # off-session but still a live 24/7 market

    @staticmethod
    def next_overlap_start(ts: datetime) -> datetime:
        """Return the next 13:00 UTC (overlap open) strictly after ts."""
        ts = _to_utc(ts)
        candidate = ts.replace(hour=13, minute=0, second=0, microsecond=0)
        if candidate <= ts:
            candidate = candidate + timedelta(days=1)
        return candidate
