"""Strategy health from the journal: auto-bench decaying strategies via rolling PSR."""

import numpy as np

from core.analysis.health import strategy_health
from memory.journal import JournalEntry


def _entry(strategy: str, pnl_pct: float) -> JournalEntry:
    return JournalEntry(
        symbol="BTCUSDT", strategy_id=strategy, session_label="ny", regime="trend",
        thesis="t", entry_price=100, exit_price=100 * (1 + pnl_pct / 100),
        qty=1.0, pnl=pnl_pct, pnl_pct=pnl_pct,
    )


def _entries(strategy: str, mean_pct: float, n: int, seed: int = 0) -> list[JournalEntry]:
    rng = np.random.default_rng(seed)
    return [_entry(strategy, float(p)) for p in rng.normal(mean_pct, 1.0, n)]


def test_losing_strategy_benched():
    h = strategy_health(_entries("momentum_trend", -1.2, 30), "momentum_trend", min_trades=20)
    assert h.benched is True
    assert h.n == 30


def test_winning_strategy_not_benched():
    h = strategy_health(_entries("momentum_trend", 1.5, 30), "momentum_trend", min_trades=20)
    assert h.benched is False
    assert h.win_rate > 0.7


def test_too_few_trades_not_benched():
    h = strategy_health(_entries("momentum_trend", -1.2, 5), "momentum_trend", min_trades=20)
    assert h.benched is False


def test_filters_by_strategy():
    trades = _entries("momentum_trend", -1.2, 25) + _entries("mean_reversion_statarb", 1.5, 25, seed=1)
    assert strategy_health(trades, "momentum_trend", min_trades=20).benched is True
    assert strategy_health(trades, "mean_reversion_statarb", min_trades=20).benched is False
