"""Lightweight indicators computed from a kline series for the scanner snapshot."""

from __future__ import annotations

import numpy as np

from core.execution.exchange import Kline


def _closes(klines: list[Kline]) -> np.ndarray:
    return np.array([k.close for k in klines], dtype=float)


def atr(klines: list[Kline], period: int = 14) -> float:
    """Average True Range over the last `period` bars."""
    n = min(period, len(klines) - 1)
    if n <= 0:
        return 0.0
    trs = [
        max(klines[i].high - klines[i].low,
            abs(klines[i].high - klines[i - 1].close),
            abs(klines[i].low - klines[i - 1].close))
        for i in range(len(klines) - n, len(klines))
    ]
    return sum(trs) / len(trs)


def trend_score(klines: list[Kline], fast: int = 20, slow: int = 50) -> float:
    """+1 strong uptrend … -1 strong downtrend, from normalized MA gap."""
    c = _closes(klines)
    if len(c) < slow:
        return 0.0
    fast_ma = c[-fast:].mean()
    slow_ma = c[-slow:].mean()
    if slow_ma == 0:
        return 0.0
    gap = (fast_ma - slow_ma) / slow_ma
    return float(np.tanh(gap * 20))


def zscore(klines: list[Kline], lookback: int = 50) -> float:
    """Z-score of the latest close vs a rolling mean/std."""
    c = _closes(klines)
    if len(c) < lookback:
        return 0.0
    window = c[-lookback:]
    sd = window.std()
    if sd == 0:
        return 0.0
    return float((c[-1] - window.mean()) / sd)


def realized_vol_pct(klines: list[Kline], lookback: int = 24, bars_per_year: float = 8760) -> float:
    """Annualized realized volatility (%) from log returns over `lookback` bars."""
    c = _closes(klines)
    if len(c) < lookback + 1:
        return 0.0
    rets = np.diff(np.log(c[-(lookback + 1):]))
    return float(rets.std() * np.sqrt(bars_per_year) * 100.0)


def volume_spike_ratio(klines: list[Kline], lookback: int = 24) -> float:
    """Latest bar volume vs trailing average — a pump/anomaly signal."""
    if len(klines) < lookback + 1:
        return 1.0
    vols = np.array([k.volume for k in klines[-(lookback + 1):]], dtype=float)
    trailing = vols[:-1].mean()
    if trailing <= 0:
        return 1.0
    return float(vols[-1] / trailing)


def pct_move(klines: list[Kline], bars: int) -> float:
    """Percent price move over the last `bars` bars."""
    c = _closes(klines)
    if len(c) < bars + 1 or c[-(bars + 1)] == 0:
        return 0.0
    return float((c[-1] / c[-(bars + 1)] - 1.0) * 100.0)
