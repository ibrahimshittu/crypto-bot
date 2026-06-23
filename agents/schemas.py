"""Structured outputs shared by the agents and the orchestrator."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SentimentBrief(BaseModel):
    """News/sentiment agent output — fact separated from opinion (FS-ReasoningAgent)."""

    symbol: str
    fact_summary: str = Field(default="", description="objective, verifiable events")
    subjective_summary: str = Field(default="", description="opinion / crowd mood")
    sentiment_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    catalysts: list[str] = Field(default_factory=list)


class StrategyDecision(BaseModel):
    """Strategy agent output — which validated strategy to apply and the intended trade."""

    symbol: str
    strategy_id: str
    action: str = Field(description="long | short | flat")
    target_position: float = Field(ge=-1.0, le=1.0)
    entry_price: float
    stop_price: float
    take_profit: float = Field(description="required — derived from your analysis, never null")
    leverage: float = 1.0
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str = ""


class CycleDecision(BaseModel):
    """Orchestrator's per-cycle summary."""

    session_label: str
    liquidity_score: float
    n_candidates: int
    n_signals: int
    n_orders: int
    n_pending_approval: int
    notes: list[str] = Field(default_factory=list)


class Lesson(BaseModel):
    """Reflection agent output — verbal-reinforcement lesson for future cycles."""

    scope: str = Field(description="strategy/session/regime the lesson applies to")
    lesson: str
    weight: float = Field(default=1.0, ge=0.0, le=5.0)
