"""Live derivative features: funding history + open interest via the exchange."""

from core.execution import PaperExchange
from core.execution.exchange import ExchangeClient


async def test_paper_funding_and_oi_roundtrip():
    ex = PaperExchange()
    assert isinstance(ex, ExchangeClient)
    ex.set_funding_history("BTCUSDT", [0.0001, 0.0002, 0.0003])
    ex.set_open_interest("BTCUSDT", [1000.0, 1100.0, 1200.0])

    fh = await ex.get_funding_history("BTCUSDT", "linear")
    oi = await ex.get_open_interest("BTCUSDT", "linear")
    assert fh == [0.0001, 0.0002, 0.0003]
    assert oi[-1] == 1200.0


async def test_enrich_candidate_adds_derivatives():
    import numpy as np

    from agents.deps import TradingDeps
    from agents.orchestrator import _enrich_candidate
    from core.config import Settings, TradingEnv
    from core.execution.exchange import Kline
    from core.screener.scanner import Candidate, InstrumentSnapshot

    ex = PaperExchange()
    ex.set_funding_history("BTCUSDT", [0.0001, 0.0002, 0.0004])  # rising
    ex.set_open_interest("BTCUSDT", [1000.0, 1200.0])            # +20%
    klines = [Kline(i * 3600_000, 100, 101, 99, 100, 1000.0) for i in range(60)]
    ex.set_klines("BTCUSDT", klines)

    snap = InstrumentSnapshot("BTCUSDT", "linear", 100.0, 5e8, 2.0, 1e6, 0.5, 1.0, 1.2, 60.0, 0.1, 0.0)
    cand = Candidate("BTCUSDT", "linear", 1.0, "momentum_trend", "x", snap)
    deps = TradingDeps(exchange=ex, settings=Settings(trading_env=TradingEnv.DEMO))

    import pytest

    enriched = await _enrich_candidate(deps, cand, klines)
    assert enriched.snapshot.funding_trend > 0
    assert enriched.snapshot.oi_change_pct == pytest.approx(20.0)
