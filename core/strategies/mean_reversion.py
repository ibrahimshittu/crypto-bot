"""Mean-reversion / stat-arb pairs — see knowledge/strategies/mean_reversion_statarb.md."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategies.base import Strategy


class MeanReversionPairsStrategy(Strategy):
    id = "mean_reversion_statarb"
    family = "market_neutral"
    products = ("spot", "linear")

    @staticmethod
    def default_params() -> dict:
        return {
            "lookback_bars": 200,
            "z_enter": 2.0,
            "z_exit": 0.3,
            "z_stop": 3.5,
        }

    def _zscore(self, series: pd.Series) -> pd.Series:
        lb = self.params["lookback_bars"]
        mean = series.rolling(lb).mean()
        std = series.rolling(lb).std(ddof=0)
        return (series - mean) / std.replace(0.0, np.nan)

    def _position_from_z(self, z: pd.Series) -> pd.Series:
        p = self.params
        pos = pd.Series(0.0, index=z.index)
        state = 0.0
        out = []
        for zi in z.to_numpy():
            if not np.isfinite(zi):
                out.append(0.0)
                continue
            if state == 0.0:
                if zi >= p["z_enter"]:
                    state = -1.0
                elif zi <= -p["z_enter"]:
                    state = 1.0
            else:
                if abs(zi) <= p["z_exit"]:
                    state = 0.0
                elif abs(zi) >= p["z_stop"]:
                    state = 0.0  # blew through entry band → cut: cointegration likely broke
            out.append(state)
        pos[:] = out
        return pos

    def positions(self, data: pd.DataFrame) -> pd.Series:
        """Single-series mean reversion on close (scanner-friendly)."""
        z = self._zscore(data["close"].astype(float))
        return self._position_from_z(z).shift(1).fillna(0.0)

    def pair_positions(self, close_a: pd.Series, close_b: pd.Series) -> pd.Series:
        """Spread z-score positions for asset A (long A / short B when +1)."""
        lb = self.params["lookback_bars"]
        a = np.log(close_a.astype(float))
        b = np.log(close_b.astype(float))
        cov = a.rolling(lb).cov(b)
        var = b.rolling(lb).var()
        beta = (cov / var).clip(-5, 5)
        spread = a - beta * b
        z = self._zscore(spread)
        return self._position_from_z(z).shift(1).fillna(0.0)
