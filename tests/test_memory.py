"""Tests for the self-improvement loop: journal + deterministic reflection + weights."""

from agents.schemas import Lesson
from memory.journal import InMemoryJournal, JournalEntry
from memory.reflection import DeterministicReflector, StrategyWeights


def _entry(strategy="momentum_trend", session="asia", pnl_pct=1.0) -> JournalEntry:
    return JournalEntry(
        symbol="BTCUSDT", strategy_id=strategy, session_label=session, regime="trend",
        thesis="t", entry_price=100, exit_price=100 * (1 + pnl_pct / 100),
        qty=1.0, pnl=pnl_pct, pnl_pct=pnl_pct,
    )


async def test_journal_records_and_reports_win_rate():
    j = InMemoryJournal()
    for pnl in (1, -1, 1, 1):
        await j.record_trade(_entry(pnl_pct=pnl))
    assert await j.win_rate("momentum_trend") == 0.75


async def test_lessons_sorted_by_weight():
    j = InMemoryJournal()
    await j.add_lesson(Lesson(scope="a", lesson="low", weight=1.0))
    await j.add_lesson(Lesson(scope="b", lesson="high", weight=3.0))
    out = await j.lessons_for()
    assert out[0].lesson == "high"


def test_reflector_downweights_losing_context():
    trades = [_entry(session="asia", pnl_pct=-2.0) for _ in range(12)]
    weights = StrategyWeights()
    lessons = DeterministicReflector().reflect(trades, weights)
    assert any("down-weight" in l.lesson or "avoid" in l.lesson for l in lessons)
    assert weights.get("momentum_trend") < 1.0  # nudged down


def test_reflector_upweights_winning_context():
    trades = [_entry(session="london_ny_overlap", pnl_pct=2.0) for _ in range(12)]
    weights = StrategyWeights()
    lessons = DeterministicReflector().reflect(trades, weights)
    assert any("up-weight" in l.lesson or "keep" in l.lesson for l in lessons)
    assert weights.get("momentum_trend") > 1.0


def test_reflector_ignores_thin_samples():
    trades = [_entry(pnl_pct=-2.0) for _ in range(3)]  # below min_trades
    weights = StrategyWeights()
    assert DeterministicReflector().reflect(trades, weights) == []


def test_strategy_weights_clamped():
    w = StrategyWeights()
    for _ in range(50):
        w.nudge("x", +1.0)
    assert w.get("x") <= 1.5
    for _ in range(50):
        w.nudge("x", -1.0)
    assert w.get("x") >= 0.0
