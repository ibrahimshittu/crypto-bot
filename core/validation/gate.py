"""The validation gate: the single decision point for whether a strategy may trade."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.validation.costs import CostModel
from core.validation.metrics import (
    bars_per_year,
    deflated_sharpe_ratio,
    max_drawdown,
    sharpe_ratio,
)
from core.validation.splits import combinatorial_purged_splits


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: list[str]
    median_oos_sharpe: float
    deflated_sharpe: float
    worst_drawdown: float
    n_folds: int
    net_sharpe_full: float
    detail: dict = field(default_factory=dict)

    def summary(self) -> str:
        verdict = "PASS" if self.passed else "REJECT"
        return (
            f"[{verdict}] median OOS Sharpe={self.median_oos_sharpe:.2f} "
            f"DSR={self.deflated_sharpe:.2f} maxDD={self.worst_drawdown:.1%} "
            f"folds={self.n_folds} | {'; '.join(self.reasons)}"
        )


def validate_strategy(
    returns: np.ndarray,
    positions: np.ndarray,
    *,
    interval_minutes: int = 60,
    n_trials: int = 1,
    cost_model: CostModel | None = None,
    sharpe_floor: float = 0.5,
    dsr_floor: float = 0.90,
    max_dd_limit: float = 0.35,
    n_groups: int = 6,
    n_test_groups: int = 2,
    participation: float = 0.0,
    daily_vol: float = 0.0,
) -> GateResult:
    """Run the gate.

    returns:   per-bar asset returns (e.g. close.pct_change()).
    positions: position held going into each bar (the strategy signal), same length.
    n_trials:  number of parameter combinations explored to find this config — the DSR
               deflates the Sharpe by this. BE HONEST here; under-reporting trials is how
               overfit strategies sneak through.
    """
    returns = np.asarray(returns, dtype=float)
    positions = np.asarray(positions, dtype=float)
    if returns.shape != positions.shape:
        raise ValueError("returns and positions must have the same shape")

    cost_model = cost_model or CostModel()
    ppy = bars_per_year(interval_minutes)

    net_full = cost_model.apply_to_returns(
        returns, positions, participation=participation, daily_vol=daily_vol
    )
    net_full = np.nan_to_num(net_full, nan=0.0)

    splits = combinatorial_purged_splits(
        len(returns), n_groups=n_groups, n_test_groups=n_test_groups
    )
    fold_sharpes: list[float] = []
    worst_dd = 0.0
    for sp in splits:
        fold_ret = net_full[sp.test_idx]
        if fold_ret.size < 8:
            continue
        fold_sharpes.append(sharpe_ratio(fold_ret, periods_per_year=ppy))
        worst_dd = min(worst_dd, max_drawdown(fold_ret))

    median_oos = float(np.median(fold_sharpes)) if fold_sharpes else 0.0
    dsr = deflated_sharpe_ratio(net_full, n_trials=n_trials)
    net_sharpe_full = sharpe_ratio(net_full, periods_per_year=ppy)

    reasons: list[str] = []
    if median_oos <= sharpe_floor:
        reasons.append(f"median OOS Sharpe {median_oos:.2f} <= floor {sharpe_floor}")
    if dsr <= dsr_floor:
        reasons.append(f"DSR {dsr:.2f} <= floor {dsr_floor} (likely overfit / N={n_trials})")
    if worst_dd < -abs(max_dd_limit):
        reasons.append(f"worst-fold drawdown {worst_dd:.1%} breaches {-abs(max_dd_limit):.0%}")

    passed = not reasons
    if passed:
        reasons.append("all gate criteria satisfied")

    return GateResult(
        passed=passed,
        reasons=reasons,
        median_oos_sharpe=median_oos,
        deflated_sharpe=dsr,
        worst_drawdown=worst_dd,
        n_folds=len(fold_sharpes),
        net_sharpe_full=net_sharpe_full,
        detail={"n_trials": n_trials, "fold_sharpes": fold_sharpes},
    )
