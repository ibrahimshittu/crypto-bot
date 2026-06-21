"""Pre-trade edge estimate: expectancy + fractional-Kelly from the strategy's recent net returns."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.execution.exchange import Kline
from core.strategies import build_strategy
from core.validation.costs import CostModel


@dataclass(frozen=True)
class EdgeEstimate:
    win_prob: float
    payoff: float
    expectancy_net: float   # mean per-bar net return while in a position
    kelly_fraction: float   # half-Kelly, clamped to [0, 0.25]


def _frame(klines: list[Kline]) -> pd.DataFrame:
    return pd.DataFrame({
        "open": [k.open for k in klines], "high": [k.high for k in klines],
        "low": [k.low for k in klines], "close": [k.close for k in klines],
        "volume": [k.volume for k in klines],
    })


def estimate_edge(klines: list[Kline], strategy_id: str, cost_model: CostModel | None = None) -> EdgeEstimate:
    cost_model = cost_model or CostModel()
    if len(klines) < 100:
        return EdgeEstimate(0.0, 0.0, 0.0, 0.0)

    df = _frame(klines)
    positions = build_strategy(strategy_id).positions(df).to_numpy()
    returns = df["close"].pct_change().fillna(0.0).to_numpy()
    net = cost_model.apply_to_returns(returns, positions)
    active = net[positions != 0]
    if active.size < 10:
        return EdgeEstimate(0.0, 0.0, 0.0, 0.0)

    wins, losses = active[active > 0], active[active < 0]
    win_prob = float(wins.size / active.size)
    avg_win = float(wins.mean()) if wins.size else 0.0
    avg_loss = float(-losses.mean()) if losses.size else 0.0
    payoff = avg_win / avg_loss if avg_loss > 0 else 0.0
    expectancy = float(active.mean())

    kelly = 0.0
    if expectancy > 0:
        if payoff > 0:
            full = (win_prob * payoff - (1 - win_prob)) / payoff
            kelly = max(0.0, min(0.25, full * 0.5))  # half-Kelly, capped
        else:  # all wins, no losses → maximal edge, take the cap
            kelly = 0.25
    return EdgeEstimate(win_prob, payoff, expectancy, kelly)
