"""Position sizing — always a fraction of LIVE equity, never a fixed dollar amount."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizingResult:
    qty: float                  # units of the base asset (e.g. BTC)
    notional: float             # qty * entry_price, in quote currency
    risk_amount: float          # quote currency at risk if stop is hit
    reason: str
    ok: bool = True


def fractional_kelly(win_rate: float, win_loss_ratio: float, fraction: float = 0.2) -> float:
    """Return a capital fraction to risk via fractional Kelly, clamped to [0, 0.25]."""
    p = max(0.0, min(1.0, win_rate))
    q = 1.0 - p
    b = max(1e-9, win_loss_ratio)
    full = (p * b - q) / b
    return max(0.0, min(0.25, full * fraction))


def position_size(
    *,
    equity: float,
    entry_price: float,
    stop_price: float,
    risk_per_trade_pct: float,
    max_position_pct: float,
    min_order_qty: float = 0.0,
    min_order_notional: float = 0.0,
    leverage: float = 1.0,
) -> SizingResult:
    """Size a position so that hitting the stop loses ~`risk_per_trade_pct`% of equity."""
    if equity <= 0 or entry_price <= 0:
        return SizingResult(0, 0, 0, "non-positive equity or price", ok=False)

    stop_dist = abs(entry_price - stop_price)
    if stop_dist <= 0:
        return SizingResult(0, 0, 0, "stop distance is zero", ok=False)

    risk_amount = equity * (risk_per_trade_pct / 100.0)
    qty = risk_amount / stop_dist

    max_notional = equity * (max_position_pct / 100.0) * max(1.0, leverage)
    if qty * entry_price > max_notional:
        qty = max_notional / entry_price
        risk_amount = qty * stop_dist

    notional = qty * entry_price

    # Reject rather than oversize a tiny account up to the exchange minimum.
    if min_order_qty and qty < min_order_qty:
        return SizingResult(
            qty, notional, risk_amount,
            f"risk-sized qty {qty:.8f} < exchange min {min_order_qty}", ok=False,
        )
    if min_order_notional and notional < min_order_notional:
        return SizingResult(
            qty, notional, risk_amount,
            f"notional {notional:.2f} < exchange min {min_order_notional}", ok=False,
        )

    return SizingResult(qty, notional, risk_amount, "sized from live equity", ok=True)
