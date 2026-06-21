"""Strategy registry — maps strategy ids to classes and builds instances."""

from __future__ import annotations

from typing import Any

from core.strategies.base import Strategy
from core.strategies.funding_carry import FundingCarryStrategy
from core.strategies.mean_reversion import MeanReversionPairsStrategy
from core.strategies.momentum import MomentumStrategy

STRATEGY_REGISTRY: dict[str, type[Strategy]] = {
    MomentumStrategy.id: MomentumStrategy,
    MeanReversionPairsStrategy.id: MeanReversionPairsStrategy,
    FundingCarryStrategy.id: FundingCarryStrategy,
}


def list_strategies() -> list[str]:
    return list(STRATEGY_REGISTRY)


def build_strategy(strategy_id: str, params: dict[str, Any] | None = None) -> Strategy:
    if strategy_id not in STRATEGY_REGISTRY:
        raise KeyError(f"unknown strategy '{strategy_id}'; known: {list_strategies()}")
    return STRATEGY_REGISTRY[strategy_id](params)
