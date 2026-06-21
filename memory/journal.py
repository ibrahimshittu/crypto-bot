"""Trade journal + lesson store for the self-improvement loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from agents.schemas import Lesson


@dataclass
class JournalEntry:
    symbol: str
    strategy_id: str
    session_label: str
    regime: str
    thesis: str
    entry_price: float
    exit_price: float
    qty: float
    pnl: float
    pnl_pct: float
    expected_slippage: float = 0.0
    realized_slippage: float = 0.0
    meta: dict = field(default_factory=dict)


class JournalStore(Protocol):
    async def record_trade(self, entry: JournalEntry) -> None: ...
    async def recent_trades(self, limit: int = 100) -> list[JournalEntry]: ...
    async def add_lesson(self, lesson: Lesson) -> None: ...
    async def lessons_for(self, scope: str | None = None, limit: int = 20) -> list[Lesson]: ...


class InMemoryJournal:
    """Default store. Deterministic and testable; also the demo backend."""

    def __init__(self) -> None:
        self._trades: list[JournalEntry] = []
        self._lessons: list[Lesson] = []

    async def record_trade(self, entry: JournalEntry) -> None:
        self._trades.append(entry)

    async def recent_trades(self, limit: int = 100) -> list[JournalEntry]:
        return self._trades[-limit:]

    async def add_lesson(self, lesson: Lesson) -> None:
        self._lessons.append(lesson)

    async def lessons_for(self, scope: str | None = None, limit: int = 20) -> list[Lesson]:
        items = self._lessons
        if scope:
            items = [l for l in items if scope in l.scope or l.scope in scope]
        return sorted(items, key=lambda l: l.weight, reverse=True)[:limit]

    async def win_rate(self, strategy_id: str) -> float:
        rel = [t for t in self._trades if t.strategy_id == strategy_id]
        if not rel:
            return 0.0
        wins = sum(1 for t in rel if t.pnl > 0)
        return wins / len(rel)
