"""Strategy base class + signal type."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StrategySignal:
    """A point-in-time trading intent emitted for the most recent bar."""

    strategy_id: str
    symbol: str
    target_position: float
    confidence: float
    rationale: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def direction(self) -> str:
        if self.target_position > 0:
            return "long"
        if self.target_position < 0:
            return "short"
        return "flat"


class Strategy(ABC):
    """Uniform interface for every strategy family."""

    id: str = "base"
    family: str = "base"
    products: tuple[str, ...] = ("spot", "linear")

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = {**self.default_params(), **(params or {})}

    @staticmethod
    def default_params() -> dict[str, Any]:
        return {}

    @abstractmethod
    def positions(self, data: pd.DataFrame) -> pd.Series:
        """Return a target-position series in [-1, 1] aligned to `data`'s index."""
        raise NotImplementedError

    def signal(self, data: pd.DataFrame, symbol: str) -> StrategySignal:
        """Convenience: the latest position as a StrategySignal."""
        pos = self.positions(data)
        last = float(pos.iloc[-1]) if len(pos) else 0.0
        return StrategySignal(
            strategy_id=self.id,
            symbol=symbol,
            target_position=last,
            confidence=min(1.0, abs(last)),
            rationale=f"{self.id} target={last:+.2f}",
        )

    @staticmethod
    def _bar_returns(close: pd.Series) -> np.ndarray:
        return close.pct_change().fillna(0.0).to_numpy()
