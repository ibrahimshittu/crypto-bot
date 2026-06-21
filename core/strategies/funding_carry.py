"""Funding-rate / cash-and-carry — see knowledge/strategies/funding_carry_basis.md."""

from __future__ import annotations

import pandas as pd

from core.strategies.base import Strategy, StrategySignal


class FundingCarryStrategy(Strategy):
    id = "funding_carry_basis"
    family = "market_neutral_carry"
    products = ("linear",)

    @staticmethod
    def default_params() -> dict:
        return {
            "min_annualized_funding_pct": 10.0,
            "exit_annualized_funding_pct": 3.0,
            "funding_interval_hours": 8.0,
        }

    def _annualized(self, funding_rate: pd.Series) -> pd.Series:
        periods_per_year = (24.0 / self.params["funding_interval_hours"]) * 365.0
        return funding_rate * periods_per_year * 100.0

    def positions(self, data: pd.DataFrame) -> pd.Series:
        """`data` must contain a 'funding_rate' column (per-interval fraction)."""
        if "funding_rate" not in data.columns:
            return pd.Series(0.0, index=data.index)
        ann = self._annualized(data["funding_rate"].astype(float))
        p = self.params
        pos = pd.Series(0.0, index=data.index)
        state = 0.0
        out = []
        for a in ann.to_numpy():
            if state == 0.0 and a >= p["min_annualized_funding_pct"]:
                state = 1.0
            elif state == 1.0 and a <= p["exit_annualized_funding_pct"]:
                state = 0.0
            out.append(state)
        pos[:] = out
        return pos.shift(1).fillna(0.0)

    def signal(self, data: pd.DataFrame, symbol: str) -> StrategySignal:
        pos = self.positions(data)
        last = float(pos.iloc[-1]) if len(pos) else 0.0
        ann = self._annualized(data["funding_rate"]).iloc[-1] if "funding_rate" in data else 0.0
        return StrategySignal(
            strategy_id=self.id,
            symbol=symbol,
            target_position=last,
            confidence=min(1.0, abs(last)),
            rationale=f"carry {'ON' if last else 'off'} @ {ann:.1f}% annualized funding",
            meta={"annualized_funding_pct": float(ann), "delta_neutral": True},
        )
