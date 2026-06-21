"""Tests for market indicators + the snapshot→scanner pipeline (via PaperExchange)."""

import numpy as np

from core.execution import PaperExchange
from core.execution.exchange import Instrument, Kline, OrderBook, Ticker
from core.screener import UniverseScanner
from data.market import indicators as ind
from data.market.snapshots import build_universe_snapshots


def _klines(closes, vols=None) -> list[Kline]:
    vols = vols if vols is not None else [100.0] * len(closes)
    return [
        Kline(start_ms=i * 3600_000, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=v)
        for i, (c, v) in enumerate(zip(closes, vols))
    ]


def test_trend_score_positive_in_uptrend():
    kl = _klines(np.linspace(100, 200, 80))
    assert ind.trend_score(kl) > 0.5


def test_trend_score_negative_in_downtrend():
    kl = _klines(np.linspace(200, 100, 80))
    assert ind.trend_score(kl) < -0.5


def test_zscore_spikes_on_outlier():
    closes = [100.0] * 60 + [115.0]
    assert ind.zscore(_klines(closes)) > 3.0


def test_volume_spike_detects_anomaly():
    vols = [100.0] * 30 + [3000.0]
    kl = _klines([100.0] * 31, vols)
    assert ind.volume_spike_ratio(kl) > 10.0


async def test_full_pipeline_paper_to_candidates():
    ex = PaperExchange()
    # One liquid trending symbol.
    ex.add_instrument(Instrument("TRNDUSDT", "linear", "TRND", "USDT", 0.001, 0.001))
    ex.set_ticker(
        Ticker("TRNDUSDT", "linear", last_price=200.0, bid=199.9, ask=200.1,
               turnover_24h=500_000_000.0, volume_24h=1e6, funding_rate=0.0)
    )
    ex.set_orderbook(
        OrderBook("TRNDUSDT",
                  bids=[(199.9 - i * 0.1, 1000) for i in range(20)],
                  asks=[(200.1 + i * 0.1, 1000) for i in range(20)])
    )
    ex.set_klines("TRNDUSDT", _klines(np.linspace(100, 200, 100)))

    snaps = await build_universe_snapshots(ex, "linear")
    assert len(snaps) == 1
    candidates = UniverseScanner().top(snaps)
    assert candidates and candidates[0].symbol == "TRNDUSDT"
    assert candidates[0].suggested_strategy == "momentum_trend"
