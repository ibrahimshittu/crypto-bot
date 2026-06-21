"""Tests for the FastAPI control plane (TestClient + seeded paper engine)."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from agents.deps import TradingDeps
from app.main import create_app
from app.state import EngineState
from core.config import Settings, TradingEnv
from core.execution import PaperExchange
from core.execution.exchange import Instrument, Kline, OrderBook, Ticker


def _engine(env=TradingEnv.DEMO) -> EngineState:
    ex = PaperExchange(starting_equity=5000.0)
    ex.add_instrument(Instrument("TRNDUSDT", "linear", "TRND", "USDT", 0.001, 0.001, max_leverage=10))
    ex.set_ticker(Ticker("TRNDUSDT", "linear", 200.0, 199.9, 200.1, turnover_24h=5e8, volume_24h=1e6))
    ex.set_orderbook(OrderBook("TRNDUSDT",
                               bids=[(199.9 - i * 0.1, 5000) for i in range(30)],
                               asks=[(200.1 + i * 0.1, 5000) for i in range(30)]))
    ex.set_klines("TRNDUSDT", [
        Kline(i * 3600_000, c, c * 1.02, c * 0.98, c, 1000.0)
        for i, c in enumerate(np.linspace(100, 200, 120))
    ])
    deps = TradingDeps(exchange=ex, settings=Settings(trading_env=env))
    eng = EngineState(deps=deps, cycle_seconds=999)
    eng.orchestrator.set_start_of_day_equity(5000.0)
    return eng


def test_health_and_run_once():
    with TestClient(create_app(_engine())) as client:
        assert client.get("/health").json()["status"] == "ok"
        decision = client.post("/engine/run-once").json()
        assert decision["n_candidates"] >= 1
        assert decision["n_orders"] >= 1
        cycles = client.get("/cycles").json()
        assert len(cycles) == 1


def test_engine_status_reflects_activity():
    with TestClient(create_app(_engine())) as client:
        # before any cycle
        s0 = client.get("/engine/status").json()
        assert s0["running"] is False
        assert s0["phase"] == "stopped"
        assert s0["cycles_completed"] == 0
        assert s0["last_decision"] is None

        # after one cycle, status reflects it
        client.post("/engine/run-once")
        s1 = client.get("/engine/status").json()
        assert s1["cycles_completed"] == 1
        assert s1["in_progress"] is False
        assert s1["last_decision"] is not None
        assert s1["seconds_since_last_cycle"] is not None


def test_balance_and_positions_after_cycle():
    with TestClient(create_app(_engine())) as client:
        client.post("/engine/run-once")
        assert client.get("/balance").json()["equity"] == 5000.0
        positions = client.get("/positions").json()
        assert len(positions) >= 1


def test_live_approval_flow_via_api():
    with TestClient(create_app(_engine(TradingEnv.LIVE))) as client:
        client.post("/engine/run-once")
        pending = client.get("/orders/pending").json()
        assert len(pending) >= 1
        tid = pending[0]["id"]
        resp = client.post("/orders/approve", json={"ticket_id": tid}).json()
        assert resp["status"] == "submitted"
        # now no longer pending
        assert client.get("/orders/pending").json() == []


def test_approve_unknown_ticket_404():
    with TestClient(create_app(_engine(TradingEnv.LIVE))) as client:
        assert client.post("/orders/approve", json={"ticket_id": 9999}).status_code == 404


def test_reasoner_wiring():
    import pytest

    from app.main import build_trading_deps

    def cfg(**kw):
        return Settings(_env_file=None, trading_env=TradingEnv.DEMO, **kw)

    # LLM-first: no OpenRouter key → demand one.
    with pytest.raises(RuntimeError):
        build_trading_deps(cfg())

    # OpenRouter key → the LLM is the strategy reasoner; sentiment stays neutral.
    llm = build_trading_deps(cfg(openrouter_api_key="sk-or-dummy"))
    assert type(llm.strategy_reasoner).__name__ == "LLMStrategyReasoner"
    assert type(llm.sentiment_reasoner).__name__ == "NullSentimentReasoner"

    # Add an Exa key → Exa drives sentiment.
    both = build_trading_deps(cfg(openrouter_api_key="sk-or-dummy", exa_api_key="exa-dummy"))
    assert type(both.sentiment_reasoner).__name__ == "ExaSentimentReasoner"
    assert type(both.strategy_reasoner).__name__ == "LLMStrategyReasoner"
