"""End-to-end orchestrator cycle on the PaperExchange — no LLM, no network.

This is the integration contract: a trending liquid symbol flows scan → strategy →
risk → order, and a circuit breaker halts the cycle.
"""

import numpy as np

from agents.deps import TradingDeps
from agents.orchestrator import Orchestrator
from core.config import Settings, TradingEnv
from core.execution import PaperExchange
from core.execution.exchange import Instrument, Kline, OrderBook, Ticker


def _trending_klines(n=120) -> list[Kline]:
    closes = np.linspace(100, 200, n)
    return [
        Kline(start_ms=i * 3600_000, open=c, high=c * 1.02, low=c * 0.98, close=c, volume=1000.0)
        for i, c in enumerate(closes)
    ]


def _seed_trending_symbol(ex: PaperExchange, symbol="TRNDUSDT") -> None:
    ex.add_instrument(Instrument(symbol, "linear", "TRND", "USDT", 0.001, 0.001, max_leverage=10))
    ex.set_ticker(
        Ticker(symbol, "linear", last_price=200.0, bid=199.9, ask=200.1,
               turnover_24h=500_000_000.0, volume_24h=1e6, funding_rate=0.0)
    )
    ex.set_orderbook(
        OrderBook(symbol,
                  bids=[(199.9 - i * 0.1, 5000) for i in range(30)],
                  asks=[(200.1 + i * 0.1, 5000) for i in range(30)])
    )
    ex.set_klines(symbol, _trending_klines())


async def test_cycle_produces_order_on_demo():
    ex = PaperExchange(starting_equity=5000.0)
    _seed_trending_symbol(ex)
    deps = TradingDeps(exchange=ex, settings=Settings(trading_env=TradingEnv.DEMO),
                       require_validation=False)
    orch = Orchestrator(deps)
    orch.set_start_of_day_equity(5000.0)

    decision = await orch.run_cycle()
    assert decision.n_candidates >= 1
    assert decision.n_orders >= 1, decision.notes
    # On demo, orders auto-submit (not pending approval).
    assert decision.n_pending_approval == 0

    positions = await ex.get_positions("linear")
    assert len(positions) == 1


async def test_cycle_holds_for_approval_on_live():
    ex = PaperExchange(starting_equity=5000.0)
    _seed_trending_symbol(ex)
    deps = TradingDeps(exchange=ex, settings=Settings(trading_env=TradingEnv.LIVE),
                       require_validation=False)
    orch = Orchestrator(deps)
    orch.set_start_of_day_equity(5000.0)

    decision = await orch.run_cycle()
    assert decision.n_orders >= 1
    # On live with no whitelist, orders wait for human approval — nothing filled.
    assert decision.n_pending_approval >= 1
    assert await ex.get_positions("linear") == []


async def test_circuit_breaker_halts_cycle():
    ex = PaperExchange(starting_equity=4000.0)  # equity already down
    _seed_trending_symbol(ex)
    deps = TradingDeps(exchange=ex, settings=Settings(trading_env=TradingEnv.DEMO,
                                                      daily_loss_halt_pct=5.0),
                       require_validation=False)
    orch = Orchestrator(deps)
    orch.set_start_of_day_equity(5000.0)  # -20% on the day → breaker

    decision = await orch.run_cycle()
    assert decision.n_orders == 0
    assert any("HALT" in n for n in decision.notes)


async def test_cycle_does_not_trade_no_edge_symbol():
    from core.validation.online import _clear_cache

    _clear_cache()
    ex = PaperExchange(starting_equity=5000.0)
    # A liquid symbol whose price is pure noise → momentum has no real edge.
    rng = np.random.default_rng(7)
    closes = np.cumprod(1 + rng.normal(0, 0.01, 400)) * 100
    noisy = [
        Kline(start_ms=i * 3600_000, open=c, high=c * 1.01, low=c * 0.99, close=c, volume=1000.0)
        for i, c in enumerate(closes)
    ]
    ex.add_instrument(Instrument("NOISEUSDT", "linear", "NOISE", "USDT", 0.001, 0.001, max_leverage=10))
    ex.set_ticker(Ticker("NOISEUSDT", "linear", last_price=float(closes[-1]), bid=closes[-1] * 0.999,
                         ask=closes[-1] * 1.001, turnover_24h=5e8, volume_24h=1e6, funding_rate=0.0))
    ex.set_orderbook(OrderBook("NOISEUSDT",
                               bids=[(closes[-1] * 0.999 - i, 5000) for i in range(30)],
                               asks=[(closes[-1] * 1.001 + i, 5000) for i in range(30)]))
    ex.set_klines("NOISEUSDT", noisy)

    deps = TradingDeps(exchange=ex, settings=Settings(trading_env=TradingEnv.DEMO),
                       require_validation=True, validation_n_trials=50)
    orch = Orchestrator(deps)
    orch.set_start_of_day_equity(5000.0)

    decision = await orch.run_cycle()
    assert decision.n_candidates >= 1          # it was scanned
    assert decision.n_orders == 0              # but no-edge noise is not traded
