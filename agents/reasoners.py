"""Reasoner protocols + deterministic defaults."""

from __future__ import annotations

from typing import Protocol

from agents.schemas import SentimentBrief, StrategyDecision
from core.execution.exchange import ExchangeClient, Kline
from core.screener.scanner import Candidate
from core.strategies import build_strategy
from data.market import indicators as ind


class SentimentReasoner(Protocol):
    async def assess(self, symbol: str) -> SentimentBrief: ...


class StrategyReasoner(Protocol):
    async def decide(
        self, candidate: Candidate, klines: list[Kline], sentiment: SentimentBrief
    ) -> StrategyDecision | None: ...


class NullSentimentReasoner:
    """No-op sentiment (neutral). Used when no news feed is configured."""

    async def assess(self, symbol: str) -> SentimentBrief:
        return SentimentBrief(symbol=symbol, confidence=0.0)


class ExaSentimentReasoner:
    """Sentiment via Exa's `answer()` — one typed call does search + cited synthesis."""

    def __init__(self, settings=None):
        from data.news.exa import ExaClient

        self.client = ExaClient(None if settings is None else settings.exa_api_key)

    async def assess(self, symbol: str) -> SentimentBrief:
        return await self.client.sentiment(symbol)


class MechanicalStrategyReasoner:
    """Deterministic strategy decision from the registered strategy library."""

    def __init__(self, atr_lookback: int = 14, atr_stop_mult: float = 2.5):
        self.atr_lookback = atr_lookback
        self.atr_stop_mult = atr_stop_mult

    async def decide(
        self, candidate: Candidate, klines: list[Kline], sentiment: SentimentBrief
    ) -> StrategyDecision | None:
        if len(klines) < 50:
            return None
        strat_id = candidate.suggested_strategy
        if strat_id == "funding_carry_basis":
            return None  # carry is handled by a dedicated delta-neutral path, not here

        import pandas as pd

        df = pd.DataFrame(
            {
                "open": [k.open for k in klines],
                "high": [k.high for k in klines],
                "low": [k.low for k in klines],
                "close": [k.close for k in klines],
                "volume": [k.volume for k in klines],
            }
        )
        target = float(build_strategy(strat_id).positions(df).iloc[-1])

        if sentiment.confidence > 0.5:
            if target > 0 and sentiment.sentiment_score < -0.5:
                target *= 0.5
            elif target < 0 and sentiment.sentiment_score > 0.5:
                target *= 0.5

        if abs(target) < 1e-6:
            return None

        price = klines[-1].close
        stop_dist = self.atr_stop_mult * (ind.atr(klines, self.atr_lookback) or price * 0.01)
        if target > 0:
            stop = price - stop_dist
            tp = price + 2 * stop_dist
            action = "long"
        else:
            stop = price + stop_dist
            tp = price - 2 * stop_dist
            action = "short"

        return StrategyDecision(
            symbol=candidate.symbol,
            strategy_id=strat_id,
            action=action,
            target_position=target,
            entry_price=price,
            stop_price=stop,
            take_profit=tp,
            leverage=1.0,
            confidence=min(1.0, abs(target)),
            rationale=f"{strat_id}: {candidate.rationale}; target={target:+.2f}",
        )


async def fetch_klines(exchange: ExchangeClient, candidate: Candidate, limit: int = 500) -> list[Kline]:
    return await exchange.get_kline(candidate.symbol, candidate.category, interval="60", limit=limit)
