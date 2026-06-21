"""Regime classifier: trend/range + volatility bucket → preferred strategy family."""

import numpy as np

from core.analysis.regime import classify_regime
from core.execution.exchange import Kline


def _klines(closes) -> list[Kline]:
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        hi = max(prev, c) * 1.0005
        lo = min(prev, c) * 0.9995
        out.append(Kline(start_ms=i * 3600_000, open=prev, high=hi, low=lo, close=c, volume=1000.0))
        prev = c
    return out


def test_trending_market_prefers_directional():
    closes = np.linspace(100, 300, 400)
    r = classify_regime(_klines(closes))
    assert r.trend == "trending"
    assert r.preferred_family == "directional"


def test_ranging_market_prefers_mean_reversion():
    rng = np.random.default_rng(3)
    closes = 100 + rng.normal(0, 1, 400)
    r = classify_regime(_klines(closes))
    assert r.trend == "ranging"
    assert r.preferred_family == "market_neutral"


def test_volatility_bucket():
    rng = np.random.default_rng(4)
    calm = classify_regime(_klines(100 + np.cumsum(rng.normal(0, 0.05, 400))))
    wild = classify_regime(_klines(100 + np.cumsum(rng.normal(0, 5.0, 400))))
    assert calm.realized_vol_pct < wild.realized_vol_pct
