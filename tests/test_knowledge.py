"""Tests for the knowledge loader — also guards that every module's frontmatter parses."""

from core import knowledge


def test_loads_all_modules():
    mods = knowledge.load_all()
    assert len(mods) >= 10  # strategies + sessions + micro + risk + exec + validation + data


def test_every_module_has_id_and_body():
    for m in knowledge.load_all():
        assert m.id, f"{m.path} missing id"
        assert m.body.strip(), f"{m.path} has empty body"


def test_strategy_families_present():
    ids = {m.id for m in knowledge.strategies()}
    expected = {
        "momentum_trend",
        "mean_reversion_statarb",
        "funding_carry_basis",
        "market_making",
        "arbitrage",
        "options_volatility",
        "order_flow_liquidation",
    }
    assert expected <= ids, f"missing: {expected - ids}"


def test_tradeable_excludes_infra_heavy():
    tradeable = {m.id for m in knowledge.tradeable_strategies()}
    # Market-making and cross-exchange arb are documented-but-excluded at our size.
    assert "market_making" not in tradeable
    assert "arbitrage" not in tradeable
    # Our core small-capital families are tradeable.
    assert {"momentum_trend", "mean_reversion_statarb", "funding_carry_basis"} <= tradeable


def test_strategy_default_params_are_structured():
    mom = knowledge.get("momentum_trend")
    assert mom is not None
    assert isinstance(mom.meta["default_params"], dict)
    assert mom.meta["default_params"]["fast_ma"] == 20


def test_risk_module_is_non_negotiable():
    risk = knowledge.get("risk")
    assert risk is not None and risk.meta.get("non_negotiable") is True
