"""Strategy library — each family produces positions from OHLCV via a uniform interface."""

from core.strategies.base import Strategy, StrategySignal
from core.strategies.funding_carry import FundingCarryStrategy
from core.strategies.mean_reversion import MeanReversionPairsStrategy
from core.strategies.momentum import MomentumStrategy
from core.strategies.registry import STRATEGY_REGISTRY, build_strategy, list_strategies

__all__ = [
    "Strategy",
    "StrategySignal",
    "MomentumStrategy",
    "MeanReversionPairsStrategy",
    "FundingCarryStrategy",
    "STRATEGY_REGISTRY",
    "build_strategy",
    "list_strategies",
]
