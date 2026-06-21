"""Recent-history validation wrapper: gate strategies on a fresh CPCV/DSR check."""

import numpy as np

from core.execution.exchange import Kline
from core.validation.online import RecentValidation, _clear_cache, validate_recent


def _klines(closes) -> list[Kline]:
    return [
        Kline(start_ms=i * 3600_000, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=1000.0)
        for i, c in enumerate(closes)
    ]


def test_random_walk_not_tradeable():
    _clear_cache()
    rng = np.random.default_rng(0)
    closes = np.cumprod(1 + rng.normal(0, 0.01, 1500)) * 100
    res = validate_recent("momentum_trend", "NOISEUSDT", _klines(closes), n_trials=50, now=0.0)
    assert isinstance(res, RecentValidation)
    assert res.tradeable is False
    assert res.deflated_sharpe < 0.95


def test_insufficient_history_not_tradeable():
    _clear_cache()
    res = validate_recent("momentum_trend", "SHORTUSDT", _klines([100.0] * 50), now=0.0)
    assert res.tradeable is False
    assert "history" in res.reason


def test_cache_hit_within_ttl(monkeypatch):
    _clear_cache()
    closes = list(np.cumprod(1 + np.random.default_rng(1).normal(0, 0.01, 1500)) * 100)
    calls = {"n": 0}
    import core.validation.online as o

    orig = o.validate_strategy

    def spy(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    monkeypatch.setattr(o, "validate_strategy", spy)
    validate_recent("momentum_trend", "BTCUSDT", _klines(closes), now=0.0)
    validate_recent("momentum_trend", "BTCUSDT", _klines(closes), now=10.0)  # within TTL → cached
    assert calls["n"] == 1


def test_cache_expires_after_ttl(monkeypatch):
    _clear_cache()
    closes = list(np.cumprod(1 + np.random.default_rng(2).normal(0, 0.01, 1500)) * 100)
    calls = {"n": 0}
    import core.validation.online as o

    orig = o.validate_strategy
    monkeypatch.setattr(o, "validate_strategy", lambda *a, **k: (calls.__setitem__("n", calls["n"] + 1), orig(*a, **k))[1])
    validate_recent("momentum_trend", "ETHUSDT", _klines(closes), ttl_seconds=100, now=0.0)
    validate_recent("momentum_trend", "ETHUSDT", _klines(closes), ttl_seconds=100, now=200.0)  # expired
    assert calls["n"] == 2
