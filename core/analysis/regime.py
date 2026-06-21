"""Classify a symbol's regime (trend/range + volatility) to route strategy selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from core.execution.exchange import Kline
from data.market import indicators as ind

Trend = Literal["trending", "ranging", "neutral"]
Volatility = Literal["calm", "normal", "elevated"]


@dataclass(frozen=True)
class RegimeState:
    trend: Trend
    volatility: Volatility
    preferred_family: str  # "directional" | "market_neutral"
    hurst: float
    adx: float
    choppiness: float
    realized_vol_pct: float


def classify_regime(klines: list[Kline]) -> RegimeState:
    adx = ind.adx(klines)
    chop = ind.choppiness(klines)
    h = ind.hurst(klines)
    rvol = ind.realized_vol_pct(klines, lookback=min(48, max(8, len(klines) // 4)))

    if adx > 25 and chop < 50:
        trend: Trend = "trending"
    elif chop > 55 or adx < 18:
        trend = "ranging"
    else:
        trend = "neutral"

    if rvol < 40:
        vol: Volatility = "calm"
    elif rvol < 100:
        vol = "normal"
    else:
        vol = "elevated"

    preferred = "directional" if trend == "trending" else "market_neutral"
    return RegimeState(trend, vol, preferred, h, adx, chop, rvol)
