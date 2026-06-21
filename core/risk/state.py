"""Portfolio state + risk decision types used by the risk engine."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.risk.sizing import SizingResult


@dataclass
class Position:
    symbol: str
    qty: float                  # signed: + long, - short
    entry_price: float
    leverage: float = 1.0
    strategy_id: str = ""


@dataclass
class PortfolioState:
    """Live snapshot the risk engine reasons over (sourced from Bybit each cycle)."""

    equity: float                               # total account equity, quote ccy
    start_of_day_equity: float                  # for the daily circuit breaker
    positions: list[Position] = field(default_factory=list)
    # rolling correlations keyed by (symbolA, symbolB) -> corr, optional
    correlations: dict[tuple[str, str], float] = field(default_factory=dict)

    @property
    def daily_pnl_pct(self) -> float:
        if self.start_of_day_equity <= 0:
            return 0.0
        return (self.equity / self.start_of_day_equity - 1.0) * 100.0

    @property
    def gross_exposure_pct(self) -> float:
        if self.equity <= 0:
            return 0.0
        gross = sum(abs(p.qty) * p.entry_price for p in self.positions)
        return gross / self.equity * 100.0


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    sizing: SizingResult | None
    reasons: list[str]
    halt_trading: bool = False  # daily circuit breaker tripped
    leverage: float = 1.0       # the EFFECTIVE (clamped) leverage to use for the order

    def summary(self) -> str:
        v = "APPROVED" if self.approved else "VETOED"
        q = f" qty={self.sizing.qty:.8f}" if self.sizing and self.sizing.ok else ""
        return f"[{v}]{q} {'; '.join(self.reasons)}"
