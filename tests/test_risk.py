"""Tests for the risk engine — capital-aware sizing + every circuit breaker/guard."""

from core.config import Settings
from core.risk import RiskEngine, position_size
from core.risk.sizing import fractional_kelly
from core.risk.state import PortfolioState, Position


def _settings(**kw) -> Settings:
    base = dict(
        risk_per_trade_pct=1.0,
        max_position_pct=20.0,
        daily_loss_halt_pct=5.0,
        max_leverage=3.0,
    )
    base.update(kw)
    return Settings(**base)


def _portfolio(equity=1000.0, sod=1000.0, positions=None) -> PortfolioState:
    return PortfolioState(
        equity=equity, start_of_day_equity=sod, positions=positions or []
    )


# ── sizing ──────────────────────────────────────────────────────────────────────
def test_size_scales_with_equity():
    """The headline guarantee: bigger capital → proportionally bigger size."""
    small = position_size(
        equity=1_000, entry_price=100, stop_price=95,
        risk_per_trade_pct=1.0, max_position_pct=50.0,
    )
    big = position_size(
        equity=10_000, entry_price=100, stop_price=95,
        risk_per_trade_pct=1.0, max_position_pct=50.0,
    )
    assert big.qty == small.qty * 10  # 10x capital → 10x size


def test_risk_amount_matches_pct():
    r = position_size(
        equity=2_000, entry_price=100, stop_price=90,
        risk_per_trade_pct=2.0, max_position_pct=100.0,
    )
    # 2% of 2000 = 40 at risk; stop dist = 10 → qty 4
    assert abs(r.risk_amount - 40.0) < 1e-6
    assert abs(r.qty - 4.0) < 1e-6


def test_max_position_cap_applies():
    r = position_size(
        equity=1_000, entry_price=100, stop_price=99.9,  # tiny stop → huge raw qty
        risk_per_trade_pct=1.0, max_position_pct=20.0,
    )
    assert r.notional <= 1_000 * 0.20 + 1e-6  # capped at 20% of equity


def test_min_order_rejects_not_oversizes():
    # equity $5, 1% risk = $0.05, stop dist $5 → qty 0.01, below a 0.05 min → REJECT
    # (the point: never round UP into oversizing a tiny account).
    r = position_size(
        equity=5, entry_price=100, stop_price=95,
        risk_per_trade_pct=1.0, max_position_pct=20.0,
        min_order_qty=0.05,
    )
    assert not r.ok and "min" in r.reason


def test_fractional_kelly_capped():
    f = fractional_kelly(win_rate=0.9, win_loss_ratio=3.0, fraction=1.0)
    assert f <= 0.25  # hard ceiling regardless of inputs


# ── engine guards ────────────────────────────────────────────────────────────────
def test_daily_circuit_breaker_halts():
    eng = RiskEngine(_settings())
    port = _portfolio(equity=940.0, sod=1000.0)  # -6% day
    d = eng.evaluate(
        portfolio=port, symbol="BTCUSDT", side="Buy",
        entry_price=100, stop_price=95,
    )
    assert not d.approved and d.halt_trading


def test_leverage_clamped_not_rejected():
    eng = RiskEngine(_settings(max_leverage=3.0))
    d = eng.evaluate(
        portfolio=_portfolio(), symbol="BTCUSDT", side="Buy",
        entry_price=100, stop_price=95, leverage=10.0,
    )
    assert d.approved
    assert any("clamped" in r for r in d.reasons)


def test_depth_gate_vetoes_illiquid():
    eng = RiskEngine(_settings(max_position_pct=100.0))
    d = eng.evaluate(
        portfolio=_portfolio(equity=100_000), symbol="SHITUSDT", side="Buy",
        entry_price=100, stop_price=95,
        depth_notional=500.0, max_depth_participation=0.1,  # only $500 of depth
    )
    assert not d.approved
    assert any("illiquid" in r or "depth" in r for r in d.reasons)


def test_correlation_budget_full_vetoes():
    eng = RiskEngine(_settings())
    d = eng.evaluate(
        portfolio=_portfolio(), symbol="ETHUSDT", side="Buy",
        entry_price=100, stop_price=95, correlation_budget_used=1.0,
    )
    assert not d.approved


def test_happy_path_approves():
    eng = RiskEngine(_settings())
    d = eng.evaluate(
        portfolio=_portfolio(equity=1000.0), symbol="BTCUSDT", side="Buy",
        entry_price=100, stop_price=95,
        depth_notional=1_000_000, min_order_qty=0.0001,
    )
    assert d.approved and d.sizing is not None and d.sizing.qty > 0
