"""Momentum / trend-following — see knowledge/strategies/momentum_trend.md."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategies.base import Strategy


class MomentumStrategy(Strategy):
    id = "momentum_trend"
    family = "directional"
    products = ("spot", "linear")

    @staticmethod
    def default_params() -> dict:
        return {
            "ts_mom_lookback": 90,
            "fast_ma": 20,
            "slow_ma": 100,
            "donchian_entry": 20,
            "trend_filter_ema": 200,
            "allow_short": True,
        }

    def positions(self, data: pd.DataFrame) -> pd.Series:
        close = data["close"].astype(float)
        p = self.params

        ts_mom = np.sign(close.pct_change(p["ts_mom_lookback"]))

        fast = close.rolling(p["fast_ma"]).mean()
        slow = close.rolling(p["slow_ma"]).mean()
        ma_cross = np.sign(fast - slow)

        hi = close.rolling(p["donchian_entry"]).max()
        lo = close.rolling(p["donchian_entry"]).min()
        breakout = pd.Series(0.0, index=close.index)
        breakout[close >= hi] = 1.0
        breakout[close <= lo] = -1.0

        vote = (ts_mom.fillna(0) + ma_cross.fillna(0) + breakout) / 3.0

        ema = close.ewm(span=p["trend_filter_ema"]).mean()
        uptrend = close > ema
        vote = vote.where(~(uptrend & (vote < 0)), 0.0)
        vote = vote.where(~(~uptrend & (vote > 0)), 0.0)

        if not p["allow_short"]:
            vote = vote.clip(lower=0.0)

        # shift(1) so bar i acts on data through i-1, never the forming bar (no look-ahead)
        return vote.shift(1).fillna(0.0).clip(-1.0, 1.0)
