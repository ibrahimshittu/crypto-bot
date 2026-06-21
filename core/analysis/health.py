"""Strategy health from realized trades: bench a strategy whose edge has decayed."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from core.validation.metrics import probabilistic_sharpe_ratio


@dataclass(frozen=True)
class StrategyHealth:
    strategy_id: str
    n: int
    win_rate: float
    psr: float
    benched: bool


def strategy_health(entries, strategy_id: str, *, min_trades: int = 20, psr_floor: float = 0.5) -> StrategyHealth:
    """Bench `strategy_id` when it has enough trades but its Probabilistic Sharpe Ratio
    (P[true Sharpe > 0], skew/kurtosis-aware) has fallen below the floor."""
    rets = np.array(
        [e.pnl_pct / 100.0 for e in entries if e.strategy_id == strategy_id], dtype=float
    )
    n = int(rets.size)
    if n < min_trades:
        win_rate = float((rets > 0).mean()) if n else 0.0
        return StrategyHealth(strategy_id, n, win_rate, 0.0, False)

    win_rate = float((rets > 0).mean())
    sd = rets.std(ddof=1)
    sr = float(rets.mean() / sd) if sd > 0 else 0.0
    psr = probabilistic_sharpe_ratio(
        sr, n=n, skew=float(stats.skew(rets)), kurtosis=float(stats.kurtosis(rets, fisher=False))
    )
    return StrategyHealth(strategy_id, n, win_rate, psr, benched=psr < psr_floor)
