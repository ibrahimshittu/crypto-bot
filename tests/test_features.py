"""Multi-timeframe confluence + crypto/stationary features."""

import numpy as np

from core.analysis.features import frac_diff_last, multiframe_confluence
from core.execution.exchange import Kline


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
