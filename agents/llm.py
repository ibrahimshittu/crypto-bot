"""LLM reasoners (Pydantic AI via OpenRouter): LLM-first strategy + reflection."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import Agent, RunContext

from agents.prompts import render
from agents.reasoners import MechanicalStrategyReasoner
from agents.schemas import Lesson, SentimentBrief, StrategyDecision
from agents.skills import build_skill_capabilities
from core.config import Settings, get_settings
from core.execution.exchange import Kline
from core.screener.scanner import Candidate
from data.market import indicators as ind
from memory.journal import JournalEntry

_TOOL_RETRIES = {"tools": 3}


def build_model(model_name: str, settings: Settings | None = None):
    s = settings or get_settings()
    from pydantic_ai.models.openai import OpenAIChatModel

    try:
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key=s.openrouter_api_key)
    except Exception:
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(base_url=s.openrouter_base_url, api_key=s.openrouter_api_key)

    return OpenAIChatModel(model_name, provider=provider)


@dataclass
class _StrategyDeps:
    candidate: Candidate
    klines: list[Kline]
    sentiment: SentimentBrief
    mech: MechanicalStrategyReasoner


class LLMStrategyReasoner:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self.ceiling = int(self.s.max_leverage)
        self._mech = MechanicalStrategyReasoner()
        self._agent = Agent(
            build_model(self.s.llm_model, self.s),
            output_type=StrategyDecision,
            deps_type=_StrategyDeps,
            retries=_TOOL_RETRIES,
            instructions=render("strategy_system", ceiling=self.ceiling),
            capabilities=build_skill_capabilities(),
        )

        @self._agent.tool
        async def deterministic_signal(ctx: RunContext[_StrategyDeps]) -> dict:
            """The validated backtested strategy's suggested direction/entry/stop (an aid)."""
            d = ctx.deps
            proposal = await d.mech.decide(d.candidate, d.klines, d.sentiment)
            return proposal.model_dump() if proposal else {"signal": "flat"}

        @self._agent.tool
        def indicators(ctx: RunContext[_StrategyDeps]) -> dict:
            """ATR, trend score, z-score and realized volatility for grounding entry/stop."""
            kl = ctx.deps.klines
            return {
                "last_price": kl[-1].close,
                "atr": ind.atr(kl),
                "trend_score": ind.trend_score(kl),
                "zscore": ind.zscore(kl),
                "realized_vol_pct": ind.realized_vol_pct(kl),
            }

    async def decide(
        self, candidate: Candidate, klines: list[Kline], sentiment: SentimentBrief
    ) -> StrategyDecision | None:
        snap = candidate.snapshot
        prompt = render(
            "strategy_decide",
            symbol=candidate.symbol, category=candidate.category,
            rationale=candidate.rationale, strategy=candidate.suggested_strategy,
            last_price=snap.last_price, vol=round(snap.realized_vol_pct),
            trend=round(snap.trend_score, 2), zscore=round(snap.zscore, 2),
            sent_score=sentiment.sentiment_score, sent_conf=sentiment.confidence,
            facts=sentiment.fact_summary, ceiling=self.ceiling,
        )
        deps = _StrategyDeps(candidate, klines, sentiment, self._mech)
        try:
            result = await self._agent.run(prompt, deps=deps)
            return result.output
        except Exception:
            return None


class ReflectionReasoner:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self._agent = Agent(
            build_model(self.s.llm_model, self.s),
            output_type=list[Lesson],
            retries=_TOOL_RETRIES,
            instructions=render("reflection_system"),
            capabilities=build_skill_capabilities(),
        )

    async def reflect(self, trades: list[JournalEntry]) -> list[Lesson]:
        if not trades:
            return []
        summary = "\n".join(
            f"{t.symbol} {t.strategy_id} {t.session_label} {t.regime} "
            f"pnl={t.pnl_pct:+.2f}% slip={t.realized_slippage:.4f}"
            for t in trades[-50:]
        )
        try:
            result = await self._agent.run(f"Recent trades:\n{summary}\n\nExtract lessons.")
            return result.output
        except Exception:
            return []
