"""Tests for the validation gate.

The headline guarantee (from the plan): the gate must REJECT a strategy that only looks
good in-sample by luck, and PASS one with a real, cost-surviving edge.
"""

import numpy as np
import pandas as pd

from core.validation import (
    CostModel,
    combinatorial_purged_splits,
    deflated_sharpe_ratio,
    triple_barrier_labels,
    validate_strategy,
)
from core.validation.metrics import max_drawdown, sharpe_ratio


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


# ── metrics ───────────────────────────────────────────────────────────────────
def test_sharpe_positive_for_upward_drift():
    r = _rng(1).normal(0.001, 0.01, 2000)
    assert sharpe_ratio(r, periods_per_year=8760) > 0


def test_max_drawdown_is_negative():
    r = np.array([0.1, -0.5, 0.05])
    assert max_drawdown(r) < 0


def test_dsr_drops_as_trials_increase():
    # Same noisy-but-slightly-positive series; more trials => lower confidence.
    r = _rng(2).normal(0.0008, 0.01, 3000)
    dsr_1 = deflated_sharpe_ratio(r, n_trials=1)
    dsr_500 = deflated_sharpe_ratio(r, n_trials=500)
    assert dsr_1 >= dsr_500


# ── CPCV splits ────────────────────────────────────────────────────────────────
def test_cpcv_no_train_test_overlap():
    splits = combinatorial_purged_splits(1000, n_groups=6, n_test_groups=2)
    assert len(splits) == 15  # C(6,2)
    for sp in splits:
        assert set(sp.train_idx).isdisjoint(set(sp.test_idx))


def test_cpcv_purges_boundary():
    # Train indices must not sit inside the embargo band right after the test block.
    splits = combinatorial_purged_splits(1000, n_groups=5, n_test_groups=1, embargo_frac=0.05)
    for sp in splits:
        tmax = sp.test_idx.max()
        band = set(range(tmax + 1, min(tmax + 51, 1000)))
        assert set(sp.train_idx).isdisjoint(band)


# ── triple-barrier ─────────────────────────────────────────────────────────────
def test_triple_barrier_labels_shape_and_values():
    close = pd.Series(np.cumprod(1 + _rng(3).normal(0, 0.01, 500)) * 100)
    out = triple_barrier_labels(close, pt_mult=2, sl_mult=2, max_hold=20)
    assert len(out) == len(close)
    assert set(out["label"].unique()) <= {-1, 0, 1}


# ── the gate: REJECT noise ──────────────────────────────────────────────────────
def test_gate_rejects_random_strategy():
    rng = _rng(42)
    returns = rng.normal(0, 0.01, 5000)          # pure noise, no edge
    positions = rng.choice([-1.0, 1.0], 5000)    # random positions
    # Pretend we tried 200 variants and kept the best — exactly the overfit scenario.
    result = validate_strategy(returns, positions, n_trials=200, sharpe_floor=0.5)
    assert not result.passed, result.summary()
    assert result.deflated_sharpe < 0.95


def test_gate_rejects_costs_eat_edge():
    # Tiny real edge that a frictionless backtest would love, but costs erase it
    # because the strategy flips position every bar (huge turnover).
    rng = _rng(7)
    returns = rng.normal(0.0002, 0.005, 4000)
    positions = np.where(np.arange(4000) % 2 == 0, 1.0, -1.0)  # flip every bar
    fat_costs = CostModel(taker_fee=0.0006, base_slippage=0.001)
    result = validate_strategy(returns, positions, n_trials=20, cost_model=fat_costs)
    assert not result.passed, result.summary()


# ── the gate: PASS a real edge ──────────────────────────────────────────────────
def test_gate_passes_genuine_edge():
    # Construct a series where position is genuinely (noisily) predictive of next return,
    # with low turnover so costs don't dominate. This is a real, persistent edge.
    rng = _rng(11)
    n = 6000
    signal = np.zeros(n)
    # Persistent regime signal (low turnover): blocks of +1 / -1.
    block = 50
    for start in range(0, n, block):
        signal[start : start + block] = rng.choice([1.0, -1.0])
    # Future return is the signal's direction * drift + noise (signal predicts return).
    returns = signal * 0.0015 + rng.normal(0, 0.008, n)
    positions = signal  # we trade in the known-predictive direction
    result = validate_strategy(
        returns, positions, n_trials=1, sharpe_floor=0.5, dsr_floor=0.90
    )
    assert result.passed, result.summary()
    assert result.median_oos_sharpe > 0.5
