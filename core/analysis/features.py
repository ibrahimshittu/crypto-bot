"""Multi-timeframe confluence + stationary (fractional-diff) features."""

from __future__ import annotations

import numpy as np

from core.execution.exchange import Kline
from data.market import indicators as ind

_MIN_BARS = 50


def _trend(klines: list[Kline]) -> float:
    return ind.trend_score(klines) if len(klines) >= _MIN_BARS else 0.0


def multiframe_confluence(k1h: list[Kline], k4h: list[Kline], k1d: list[Kline]) -> dict:
    """Trend per timeframe and how many agree with the 1h direction (0–3)."""
    t1, t4, td = _trend(k1h), _trend(k4h), _trend(k1d)
    base = np.sign(t1)
    confluence = 0
    if base != 0:
        confluence = sum(1 for t in (t1, t4, td) if np.sign(t) == base)
    return {
        "trend_1h": float(t1),
        "trend_4h": float(t4),
        "trend_1d": float(td),
        "confluence": int(confluence),
    }


def _ffd_weights(d: float, size: int) -> np.ndarray:
    w = [1.0]
    for k in range(1, size):
        w.append(-w[-1] * (d - k + 1) / k)
    return np.array(w[::-1])


def frac_diff_last(closes, d: float = 0.5, window: int = 50) -> float:
    """Fractionally-differentiated value of the latest close (stationary, memory-preserving)."""
    closes = np.asarray(closes, dtype=float)
    if len(closes) < window:
        return 0.0
    w = _ffd_weights(d, window)
    return float(np.dot(w, np.log(closes[-window:])))
