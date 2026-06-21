"""Transaction-cost and market-impact model."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CostModel:
    """Per-side cost model in fractional terms (0.001 == 0.1%).

    Bybit defaults: spot taker ~0.1%, perps taker ~0.055%. Slippage is the dominant cost
    on thin alts; impact follows the square-root law.
    """

    taker_fee: float = 0.00055      # perps taker; use 0.001 for spot
    base_slippage: float = 0.0005   # 5 bps baseline on liquid pairs
    impact_coef: float = 0.5        # Y in the square-root law, O(1)

    def round_trip_cost(self, *, participation: float = 0.0, daily_vol: float = 0.0) -> float:
        """Total fractional cost to enter AND exit one unit.

        participation = order size / average daily volume (Q/V).
        daily_vol = daily volatility (sigma) as a fraction.
        Square-root impact: I ≈ Y · σ · sqrt(Q/V), charged per side.
        """
        impact = 0.0
        if participation > 0 and daily_vol > 0:
            impact = self.impact_coef * daily_vol * float(np.sqrt(participation))
        per_side = self.taker_fee + self.base_slippage + impact
        return 2.0 * per_side

    def apply_to_returns(
        self,
        returns: np.ndarray,
        positions: np.ndarray,
        *,
        participation: float = 0.0,
        daily_vol: float = 0.0,
    ) -> np.ndarray:
        """Charge cost on every change in position (a trade).

        returns[i]   = asset return realized over bar i (already position-agnostic).
        positions[i] = position held going INTO bar i (e.g. -1/0/+1 or fractional).
        Cost is deducted whenever the position changes between consecutive bars,
        scaled by the traded size |Δposition|.
        """
        returns = np.asarray(returns, dtype=float)
        positions = np.asarray(positions, dtype=float)
        strat_ret = positions * returns

        turnover = np.abs(np.diff(positions, prepend=0.0))
        per_side = self.taker_fee + self.base_slippage
        if participation > 0 and daily_vol > 0:
            per_side += self.impact_coef * daily_vol * float(np.sqrt(participation))
        costs = turnover * per_side
        return strat_ret - costs
