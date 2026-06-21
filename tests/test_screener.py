"""Tests for the universe scanner — gates filter junk, ranking is sane."""

from core.screener import GateConfig, UniverseScanner
from core.screener.scanner import InstrumentSnapshot


def _snap(symbol="BTCUSDT", **kw) -> InstrumentSnapshot:
    base = dict(
        symbol=symbol,
        category="linear",
        last_price=100.0,
        turnover_24h_usd=500_000_000.0,
        spread_bps=2.0,
        depth_usd_1pct=2_000_000.0,
        move_1h_pct=0.5,
        move_24h_pct=2.0,
        volume_spike_ratio=1.2,
        realized_vol_pct=60.0,
        trend_score=0.2,
        zscore=0.3,
        annualized_funding_pct=5.0,
        age_hours=10_000.0,
    )
    base.update(kw)
    return InstrumentSnapshot(**base)


def test_liquid_major_passes():
    out = UniverseScanner().scan([_snap()])
    assert len(out) == 1 and not out[0].rejected


def test_illiquid_pair_rejected():
    thin = _snap(symbol="THINUSDT", turnover_24h_usd=10_000.0, depth_usd_1pct=1_000.0)
    out = UniverseScanner().scan([thin])
    assert out[0].rejected
    assert any("turnover" in r or "depth" in r for r in out[0].reject_reasons)


def test_pump_signature_rejected():
    pump = _snap(symbol="PUMPUSDT", move_1h_pct=60.0, volume_spike_ratio=30.0)
    out = UniverseScanner().scan([pump])
    assert out[0].rejected
    assert any("parabolic" in r or "spike" in r for r in out[0].reject_reasons)


def test_new_listing_quarantined():
    fresh = _snap(symbol="NEWUSDT", age_hours=5.0)
    out = UniverseScanner().scan([fresh])
    assert out[0].rejected
    assert any("quarantine" in r for r in out[0].reject_reasons)


def test_strong_trend_suggests_momentum():
    trender = _snap(symbol="TRENDUSDT", trend_score=0.9, annualized_funding_pct=0.5, zscore=0.1)
    out = UniverseScanner().top([trender])
    assert out[0].suggested_strategy == "momentum_trend"


def test_rich_funding_suggests_carry():
    carry = _snap(symbol="CARRYUSDT", annualized_funding_pct=25.0, trend_score=0.1, zscore=0.1)
    # 25% funding is within the manipulation cap? No — max_funding_abs_pct=3.0 default.
    # Use a config that allows higher funding for this test.
    cfg = GateConfig(max_funding_abs_pct=50.0)
    out = UniverseScanner(cfg).top([carry])
    assert out[0].suggested_strategy == "funding_carry_basis"


def test_ranking_orders_by_score():
    strong = _snap(symbol="STRONGUSDT", trend_score=0.95, annualized_funding_pct=0.5)
    weak = _snap(symbol="WEAKUSDT", trend_score=0.05, annualized_funding_pct=0.5, zscore=0.1)
    out = UniverseScanner().top([weak, strong])
    assert out[0].symbol == "STRONGUSDT"
