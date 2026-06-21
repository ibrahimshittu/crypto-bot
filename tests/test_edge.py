"""Pre-trade edge estimate (expectancy net of costs) + edge-scaled sizing."""

import numpy as np

from core.analysis.edge import estimate_edge
from core.execution.exchange import Kline
from core.risk.sizing import edge_scaled_size, position_size


def _klines(closes) -> list[Kline]:
    return [
        Kline(start_ms=i * 3600_000, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=1000.0)
        for i, c in enumerate(closes)
    ]


def test_edge_positive_for_real_trend():
    closes = np.linspace(100, 260, 600)  # persistent uptrend momentum can ride
    e = estimate_edge(_klines(closes), "momentum_trend")
    assert e.expectancy_net > 0
    assert e.kelly_fraction > 0


def test_edge_nonpositive_for_noise():
    closes = np.cumprod(1 + np.random.default_rng(0).normal(0, 0.01, 600)) * 100
    e = estimate_edge(_klines(closes), "momentum_trend")
    assert e.kelly_fraction == 0.0 or e.expectancy_net <= 0


def test_edge_scaled_size_grows_with_edge():
    base = position_size(equity=1000, entry_price=100, stop_price=95,
                         risk_per_trade_pct=1.0, max_position_pct=100.0)
    weak = edge_scaled_size(base, kelly_fraction=0.005)
    strong = edge_scaled_size(base, kelly_fraction=0.06)
    assert strong.qty > weak.qty
    assert strong.qty <= base.qty * 2.0 + 1e-9  # capped
