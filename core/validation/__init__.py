"""Backtest validation: the gatekeeper that decides what may risk capital."""

from core.validation.costs import CostModel
from core.validation.gate import GateResult, validate_strategy
from core.validation.labeling import triple_barrier_labels
from core.validation.online import RecentValidation, validate_recent
from core.validation.metrics import deflated_sharpe_ratio, sharpe_ratio
from core.validation.splits import combinatorial_purged_splits

__all__ = [
    "CostModel",
    "GateResult",
    "validate_strategy",
    "validate_recent",
    "RecentValidation",
    "triple_barrier_labels",
    "deflated_sharpe_ratio",
    "sharpe_ratio",
    "combinatorial_purged_splits",
]
