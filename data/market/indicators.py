"""Lightweight indicators computed from a kline series for the scanner snapshot."""

from __future__ import annotations

import numpy as np

from core.execution.exchange import Kline


def _closes(klines: list[Kline]) -> np.ndarray:
    return np.array([k.close for k in klines], dtype=float)


def hurst(klines: list[Kline], max_lag: int = 50) -> float:
    """Hurst exponent of the close series. >0.5 trending, <0.5 mean-reverting, ~0.5 random."""
    c = _closes(klines)
    if len(c) < max_lag * 2:
        max_lag = max(4, len(c) // 4)
    lags = np.arange(2, max_lag)
    tau = []
    for lag in lags:
        diff = c[lag:] - c[:-lag]
        sd = diff.std()
        tau.append(sd if sd > 1e-12 else 1e-12)
    slope = np.polyfit(np.log(lags), np.log(tau), 1)[0]
    return float(slope)


def adx(klines: list[Kline], period: int = 14) -> float:
    """Wilder's Average Directional Index (0–100). >25 indicates a real trend."""
    if len(klines) < period * 2 + 1:
        return 0.0
    high = np.array([k.high for k in klines])
    low = np.array([k.low for k in klines])
    close = np.array([k.close for k in klines])
    up = high[1:] - high[:-1]
    down = low[:-1] - low[1:]
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = np.maximum.reduce([
        high[1:] - low[1:],
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:] - close[:-1]),
    ])

    def _smooth(x):
        out = np.zeros_like(x)
        out[period - 1] = x[:period].sum()
        for i in range(period, len(x)):
            out[i] = out[i - 1] - out[i - 1] / period + x[i]
        return out[period - 1:]

    tr_s, plus_s, minus_s = _smooth(tr), _smooth(plus_dm), _smooth(minus_dm)
    tr_s = np.where(tr_s == 0, 1e-12, tr_s)
    plus_di = 100 * plus_s / tr_s
    minus_di = 100 * minus_s / tr_s
    denom = np.where((plus_di + minus_di) == 0, 1e-12, plus_di + minus_di)
    dx = 100 * np.abs(plus_di - minus_di) / denom
    return float(dx[-period:].mean()) if len(dx) >= period else float(dx.mean())


def choppiness(klines: list[Kline], period: int = 14) -> float:
    """Choppiness Index (0–100). >61 ranging/choppy, <38 trending."""
    if len(klines) < period + 1:
        return 50.0
    high = np.array([k.high for k in klines])
    low = np.array([k.low for k in klines])
    close = np.array([k.close for k in klines])
    tr = np.maximum.reduce([
        high[1:] - low[1:],
        np.abs(high[1:] - close[:-1]),
        np.abs(low[1:] - close[:-1]),
    ])
    tr_sum = tr[-period:].sum()
    rng = high[-period:].max() - low[-period:].min()
    if rng <= 0 or tr_sum <= 0:
        return 50.0
    return float(100 * np.log10(tr_sum / rng) / np.log10(period))


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
