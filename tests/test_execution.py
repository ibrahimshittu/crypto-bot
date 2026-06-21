"""Tests for the execution layer: paper exchange + phased approval workflow."""

import pytest

from core.config import Settings, TradingEnv
from core.execution import OrderRequest, PaperExchange
from core.execution.exchange import ExchangeClient, Instrument, Ticker
from core.execution.orders import ApprovalStatus, OrderWorkflow


def _paper() -> PaperExchange:
    ex = PaperExchange(starting_equity=1000.0)
    ex.add_instrument(
        Instrument("BTCUSDT", "linear", "BTC", "USDT", min_order_qty=0.001, qty_step=0.001,
                   max_leverage=10.0)
    )
    ex.set_ticker(
        Ticker("BTCUSDT", "linear", last_price=100.0, bid=99.9, ask=100.1,
               turnover_24h=1e9, volume_24h=1e7)
    )
    return ex


def test_paper_implements_protocol():
    assert isinstance(PaperExchange(), ExchangeClient)


async def test_paper_fills_and_tracks_position():
    ex = _paper()
    res = await ex.place_order(
        OrderRequest("BTCUSDT", "linear", "Buy", "Market", qty=0.5)
    )
    assert res.ok and res.filled_qty == 0.5
    positions = await ex.get_positions("linear")
    assert len(positions) == 1 and positions[0].side == "Buy"


async def test_paper_netting_closes_position():
    ex = _paper()
    await ex.place_order(OrderRequest("BTCUSDT", "linear", "Buy", "Market", qty=0.5))
    await ex.place_order(OrderRequest("BTCUSDT", "linear", "Sell", "Market", qty=0.5))
    assert await ex.get_positions("linear") == []


async def test_demo_env_auto_submits():
    ex = _paper()
    wf = OrderWorkflow(ex, Settings(trading_env=TradingEnv.DEMO))
    ticket = await wf.submit(OrderRequest("BTCUSDT", "linear", "Buy", "Market", qty=0.1))
    assert ticket.status == ApprovalStatus.SUBMITTED


async def test_live_env_requires_approval():
    ex = _paper()
    wf = OrderWorkflow(ex, Settings(trading_env=TradingEnv.LIVE))
    req = OrderRequest("BTCUSDT", "linear", "Buy", "Market", qty=0.1, strategy_id="momentum_trend")
    ticket = await wf.submit(req)
    assert ticket.status == ApprovalStatus.PENDING
    assert len(wf.pending()) == 1

    approved = await wf.approve(ticket.id)
    assert approved.status == ApprovalStatus.SUBMITTED
    assert wf.pending() == []


async def test_live_whitelisted_strategy_auto_submits():
    ex = _paper()
    wf = OrderWorkflow(
        ex, Settings(trading_env=TradingEnv.LIVE), auto_whitelist={"funding_carry_basis"}
    )
    req = OrderRequest("BTCUSDT", "linear", "Buy", "Market", qty=0.1, strategy_id="funding_carry_basis")
    ticket = await wf.submit(req)
    assert ticket.status == ApprovalStatus.SUBMITTED


async def test_live_reject_flow():
    ex = _paper()
    wf = OrderWorkflow(ex, Settings(trading_env=TradingEnv.LIVE))
    ticket = await wf.submit(OrderRequest("BTCUSDT", "linear", "Buy", "Market", qty=0.1))
    rejected = wf.reject(ticket.id, "looks wrong")
    assert rejected.status == ApprovalStatus.REJECTED
