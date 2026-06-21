"""Tests for the strategy library: interface, no-look-ahead, and gate integration."""

import numpy as np
import pandas as pd

from core.strategies import (
    FundingCarryStrategy,
    MeanReversionPairsStrategy,
    MomentumStrategy,
    build_strategy,
    list_strategies,
)
from core.validation import validate_strategy


def _ohlcv(close: np.ndarray) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=len(close), freq="h", tz="UTC")
    close = pd.Series(close, index=idx)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close),
            "high": close * 1.001,
            "low": close * 0.999,
            "close": close,
            "volume": 1000.0,
        }
    )


def test_registry_has_three_families():
    assert set(list_strategies()) == {
        "momentum_trend",
        "mean_reversion_statarb",
        "funding_carry_basis",
    }


def test_positions_in_range_and_aligned():
    rng = np.random.default_rng(0)
    df = _ohlcv(np.cumprod(1 + rng.normal(0, 0.01, 600)) * 100)
    for sid in list_strategies():
        if sid == "funding_carry_basis":
            continue
        pos = build_strategy(sid).positions(df)
        assert len(pos) == len(df)
        assert pos.abs().max() <= 1.0 + 1e-9


def test_momentum_no_lookahead_first_bar_flat():
    df = _ohlcv(np.linspace(100, 200, 400))
    pos = MomentumStrategy().positions(df)
    # First bar can't know anything → must be flat (shifted).
    assert pos.iloc[0] == 0.0


def test_momentum_goes_long_in_uptrend():
    df = _ohlcv(np.linspace(100, 300, 500))  # steady uptrend
    pos = MomentumStrategy().positions(df)
    assert pos.iloc[-1] > 0


def test_mean_reversion_shorts_when_overextended():
    # Flat series then a spike up → z-score high → short signal.
    base = np.full(300, 100.0)
    base[-1] = 130.0
    df = _ohlcv(base)
    z = MeanReversionPairsStrategy()._zscore(df["close"])
    assert z.iloc[-1] > 2.0


def test_funding_carry_turns_on_with_high_funding():
    idx = pd.date_range("2026-01-01", periods=50, freq="8h", tz="UTC")
    # 0.05% per 8h ≈ 54% annualized → well above the 10% entry threshold.
    df = pd.DataFrame({"funding_rate": [0.0005] * 50}, index=idx)
    sig = FundingCarryStrategy().signal(df, "BTCUSDT")
    assert sig.target_position == 1.0
    assert sig.meta["delta_neutral"] is True


def test_strategy_output_flows_through_gate():
    # A trending series + momentum strategy should produce a coherent (if not passing)
    # gate result without errors — this is the integration contract.
    rng = np.random.default_rng(5)
    close = np.cumprod(1 + rng.normal(0.0003, 0.01, 3000)) * 100
    df = _ohlcv(close)
    strat = MomentumStrategy()
    pos = strat.positions(df).to_numpy()
    returns = df["close"].pct_change().fillna(0).to_numpy()
    result = validate_strategy(returns, pos, n_trials=10)
    assert isinstance(result.passed, bool)
    assert result.n_folds > 0
