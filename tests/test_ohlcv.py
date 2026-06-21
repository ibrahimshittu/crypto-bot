"""OHLCV persistence + deep historical backtest (in-memory store, no DB)."""

import numpy as np

from core.execution.exchange import Kline
from data.db.ohlcv import InMemoryOhlcvStore, backtest_history


def _klines(closes, start=0) -> list[Kline]:
    return [
        Kline(start_ms=(start + i) * 3600_000, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=1000.0)
        for i, c in enumerate(closes)
    ]


async def test_save_dedupes_and_accumulates():
    store = InMemoryOhlcvStore()
    await store.save("BTCUSDT", "linear", "60", _klines([100, 101, 102]))
    await store.save("BTCUSDT", "linear", "60", _klines([101, 102, 103], start=1))  # overlap
    out = await store.load("BTCUSDT", "linear", "60")
    assert [round(k.close) for k in out] == [100, 101, 102, 103]  # deduped by start time


async def test_backtest_history_runs_over_stored_data():
    store = InMemoryOhlcvStore()
    closes = np.cumprod(1 + np.random.default_rng(0).normal(0, 0.01, 1500)) * 100
    await store.save("NOISEUSDT", "linear", "60", _klines(closes))
    result = await backtest_history(store, "momentum_trend", "NOISEUSDT", n_trials=50)
    assert result is not None
    assert result.passed is False  # noise has no edge over the full history


async def test_backtest_history_insufficient_returns_none():
    store = InMemoryOhlcvStore()
    await store.save("X", "linear", "60", _klines([100.0] * 50))
    assert await backtest_history(store, "momentum_trend", "X") is None
