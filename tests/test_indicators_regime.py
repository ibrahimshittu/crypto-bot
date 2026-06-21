"""Regime primitives: Hurst, ADX, choppiness."""

import numpy as np

from core.execution.exchange import Kline
from data.market.indicators import adx, choppiness, hurst


def _klines(closes, highs=None, lows=None) -> list[Kline]:
    highs = highs if highs is not None else [c * 1.005 for c in closes]
    lows = lows if lows is not None else [c * 0.995 for c in closes]
    return [
        Kline(start_ms=i * 3600_000, open=c, high=h, low=lo, close=c, volume=1000.0)
        for i, (c, h, lo) in enumerate(zip(closes, highs, lows))
    ]


def test_hurst_orders_persistence():
    # Persistent (autocorrelated) returns have a higher Hurst than mean-reverting noise.
    rng = np.random.default_rng(0)
    rets = np.zeros(600)
    for i in range(1, 600):
        rets[i] = 0.6 * rets[i - 1] + rng.normal(0, 1)
    trending = hurst(_klines(100 + np.cumsum(rets)))
    reverting = hurst(_klines(100 + rng.normal(0, 1, 600)))
    assert trending > reverting


def test_hurst_mean_reverting_below_half():
    rng = np.random.default_rng(1)
    closes = 100 + rng.normal(0, 1, 600)  # stationary noise around 100
    assert hurst(_klines(closes)) < 0.5


def test_adx_strong_in_trend():
    closes = np.linspace(100, 200, 300)
    assert adx(_klines(closes)) > 25


def test_choppiness_high_in_range():
    rng = np.random.default_rng(2)
    closes = 100 + rng.normal(0, 1, 300)
    assert choppiness(_klines(closes)) > 55
