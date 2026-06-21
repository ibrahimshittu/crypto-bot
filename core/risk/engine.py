"""RiskEngine — the deterministic gate between a signal and an order."""

from __future__ import annotations

from core.config import Settings, get_settings
from core.risk.sizing import position_size
from core.risk.state import PortfolioState, RiskDecision


class RiskEngine:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()

    def evaluate(
        self,
        *,
        portfolio: PortfolioState,
        symbol: str,
        side: str,                      # "Buy" | "Sell"
        entry_price: float,
        stop_price: float,
        leverage: float = 1.0,
        min_order_qty: float = 0.0,
        min_order_notional: float = 0.0,
        depth_notional: float | None = None,   # available book notional within slippage band
        max_depth_participation: float = 0.1,  # 0..1 fraction of book depth
        correlation_budget_used: float = 0.0,  # 0..1 fraction of correlated risk already on
    ) -> RiskDecision:
        reasons: list[str] = []

        if portfolio.daily_pnl_pct <= -abs(self.s.daily_loss_halt_pct):
            return RiskDecision(
                approved=False,
                sizing=None,
                reasons=[
                    f"daily loss {portfolio.daily_pnl_pct:.2f}% <= "
                    f"-{self.s.daily_loss_halt_pct}% → trading halted"
                ],
                halt_trading=True,
            )

        if leverage > self.s.max_leverage:
            reasons.append(f"leverage {leverage}x > cap {self.s.max_leverage}x → clamped")
            leverage = self.s.max_leverage

        sizing = position_size(
            equity=portfolio.equity,
            entry_price=entry_price,
            stop_price=stop_price,
            risk_per_trade_pct=self.s.risk_per_trade_pct,
            max_position_pct=self.s.max_position_pct,
            min_order_qty=min_order_qty,
            min_order_notional=min_order_notional,
            leverage=leverage,
        )
        if not sizing.ok:
            reasons.append(sizing.reason)
            return RiskDecision(approved=False, sizing=sizing, reasons=reasons)

        if depth_notional is not None and depth_notional > 0:
            participation = sizing.notional / depth_notional
            if participation > max_depth_participation:
                reasons.append(
                    f"order is {participation:.0%} of book depth "
                    f"(> {max_depth_participation:.0%}) → too illiquid"
                )
                return RiskDecision(approved=False, sizing=sizing, reasons=reasons)

        if correlation_budget_used >= 1.0:
            reasons.append("correlated risk budget already full → veto")
            return RiskDecision(approved=False, sizing=sizing, reasons=reasons)

        projected = portfolio.gross_exposure_pct + (
            sizing.notional / max(portfolio.equity, 1e-9) * 100.0
        )
        max_gross = self.s.max_position_pct * 5  # heuristic portfolio ceiling
        if projected > max_gross:
            reasons.append(
                f"projected gross exposure {projected:.0f}% > ceiling {max_gross:.0f}%"
            )
            return RiskDecision(approved=False, sizing=sizing, reasons=reasons)

        reasons.append(sizing.reason)
        return RiskDecision(approved=True, sizing=sizing, reasons=reasons, leverage=leverage)
