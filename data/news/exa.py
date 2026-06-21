"""Exa news/sentiment client."""

from __future__ import annotations

import asyncio
import json

from agents.schemas import SentimentBrief
from core.config import get_settings
from core.observability import span

_NAMES = {
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "XRP": "XRP (Ripple)",
    "BNB": "BNB", "DOGE": "Dogecoin", "ADA": "Cardano", "AVAX": "Avalanche",
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "fact_summary": {"type": "string"},
        "subjective_summary": {"type": "string"},
        "sentiment_score": {"type": "number"},
        "confidence": {"type": "number"},
        "catalysts": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["fact_summary", "subjective_summary", "sentiment_score", "confidence"],
}


def _base(symbol: str) -> str:
    for quote in ("USDT", "USDC", "USD", "PERP"):
        if symbol.endswith(quote):
            return symbol[: -len(quote)]
    return symbol


def _label(symbol: str) -> str:
    base = _base(symbol)
    name = _NAMES.get(base)
    return f"{name} ({base})" if name else base


def _clamp(value, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return 0.0


class ExaClient:
    def __init__(self, api_key: str | None = None, research_timeout_ms: int = 120_000):
        self.api_key = api_key if api_key is not None else get_settings().exa_api_key
        self.research_timeout_ms = research_timeout_ms

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def sentiment(self, symbol: str) -> SentimentBrief:
        if not self.api_key:
            return SentimentBrief(symbol=symbol, confidence=0.0)

        from agents.prompts import render

        system = render("sentiment_system")
        query = render("sentiment_query", label=_label(symbol))

        def _run() -> SentimentBrief:
            from exa_py import Exa

            resp = Exa(self.api_key).answer(query, system_prompt=system, output_schema=_SCHEMA)
            data = resp.answer
            if isinstance(data, str):
                data = json.loads(data)
            return SentimentBrief(
                symbol=symbol,
                fact_summary=str(data.get("fact_summary", "")),
                subjective_summary=str(data.get("subjective_summary", "")),
                sentiment_score=_clamp(data.get("sentiment_score", 0.0), -1.0, 1.0),
                confidence=_clamp(data.get("confidence", 0.0), 0.0, 1.0),
                catalysts=[str(c) for c in (data.get("catalysts") or [])],
            )

        try:
            with span("exa.sentiment", symbol=symbol) as sp:
                brief = await asyncio.to_thread(_run)
                if sp is not None:
                    sp.set_attributes({
                        "sentiment_score": brief.sentiment_score,
                        "confidence": brief.confidence,
                        "facts": brief.fact_summary,
                        "catalysts": brief.catalysts,
                    })
                return brief
        except Exception:
            return SentimentBrief(symbol=symbol, confidence=0.0)

    async def deep_research(self, symbol: str, instructions: str | None = None) -> str:
        if not self.api_key:
            return ""
        instr = instructions or (
            f"Research {_label(symbol)} cryptocurrency: recent news, on-chain and social "
            "signals, upcoming catalysts, and the main bull and bear arguments. Summarize "
            "what would move the price in the next few days."
        )

        def _run() -> str:
            from exa_py import Exa

            exa = Exa(self.api_key)
            task = exa.research.create(instructions=instr, model="exa-research")
            done = exa.research.poll_until_finished(
                task.research_id, timeout_ms=self.research_timeout_ms
            )
            out = getattr(done, "output", None) or getattr(done, "data", None) or done
            return out if isinstance(out, str) else str(out)

        try:
            with span("exa.research", symbol=symbol):
                return await asyncio.to_thread(_run)
        except Exception:
            return ""
