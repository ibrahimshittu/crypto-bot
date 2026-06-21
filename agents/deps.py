"""Dependency container shared across the trading cycle."""

from __future__ import annotations

from dataclasses import dataclass, field

from agents.reasoners import (
    MechanicalStrategyReasoner,
    NullSentimentReasoner,
    SentimentReasoner,
    StrategyReasoner,
)
from core.config import Settings, get_settings
from core.execution.exchange import ExchangeClient
from core.execution.orders import OrderWorkflow
from core.risk import RiskEngine
from core.screener import GateConfig, UniverseScanner
from core.sessions import SessionClock
from memory.journal import InMemoryJournal, JournalStore


@dataclass
class TradingDeps:
    exchange: ExchangeClient
    settings: Settings = field(default_factory=get_settings)
    risk: RiskEngine = field(default_factory=RiskEngine)
    scanner: UniverseScanner = field(default_factory=lambda: UniverseScanner(GateConfig()))
    workflow: OrderWorkflow | None = None
    journal: JournalStore = field(default_factory=InMemoryJournal)
    clock: SessionClock = field(default_factory=SessionClock)
    # Reasoners default to deterministic (no LLM) so the cycle runs anywhere.
    strategy_reasoner: StrategyReasoner = field(default_factory=MechanicalStrategyReasoner)
    sentiment_reasoner: SentimentReasoner = field(default_factory=NullSentimentReasoner)
    category: str = "linear"
    max_symbols: int | None = 100
    max_candidates: int = 25
    max_new_orders_per_cycle: int = 3
    require_validation: bool = True
    validation_n_trials: int = 25
    health_min_trades: int = 20
    ohlcv_store: object = None          # OhlcvStore | None — persist history when set

    def __post_init__(self) -> None:
        if self.workflow is None:
            self.workflow = OrderWorkflow(self.exchange, self.settings)
