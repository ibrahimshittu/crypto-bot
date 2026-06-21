"""Multi-timeframe confluence + crypto/stationary features."""

import numpy as np
import pytest

from core.analysis.features import (
    basis_pct,
    frac_diff_last,
    funding_trend,
    multiframe_confluence,
    oi_change_pct,
)
from core.execution.exchange import Kline, OrderBook
from data.market.indicators import order_book_imbalance


def _klines(closes) -> list[Kline]:
    return [
        Kline(start_ms=i * 3600_000, open=c, high=c * 1.001, low=c * 0.999, close=c, volume=1000.0)
        for i, c in enumerate(closes)
    ]


def test_confluence_all_agree():
    up = _klines(np.linspace(100, 200, 200))
    out = multiframe_confluence(up, up, up)
    assert out["confluence"] == 3
    assert out["trend_1h"] > 0


def test_confluence_partial_disagreement():
    up = _klines(np.linspace(100, 200, 200))
    down = _klines(np.linspace(200, 100, 200))
    out = multiframe_confluence(up, up, down)  # 1h+4h up, 1d down
    assert out["confluence"] == 2


def test_frac_diff_finite():
    closes = np.cumprod(1 + np.random.default_rng(0).normal(0, 0.01, 300)) * 100
    val = frac_diff_last(closes, d=0.5)
    assert np.isfinite(val)


def test_order_book_imbalance():
    bid_heavy = OrderBook("X", bids=[(100, 9000)], asks=[(101, 1000)])
    assert order_book_imbalance(bid_heavy) > 0.5
    ask_heavy = OrderBook("X", bids=[(100, 1000)], asks=[(101, 9000)])
    assert order_book_imbalance(ask_heavy) < -0.5


def test_derivatives_helpers():
    assert funding_trend([0.01, 0.02, 0.03, 0.05]) > 0       # rising funding
    assert oi_change_pct([1000, 1100]) == pytest.approx(10.0)   # +10% OI
    assert basis_pct(101.0, 100.0) == pytest.approx(1.0)        # 1% contango
