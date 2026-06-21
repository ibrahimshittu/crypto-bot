"""Round order quantities/prices to an instrument's lot step / tick size using Decimal math."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def floor_to_step(value: float, step: float) -> float:
    """Round qty DOWN to the nearest lot step (never round up into a bigger position)."""
    if not step or step <= 0:
        return float(value)
    v, s = Decimal(str(value)), Decimal(str(step))
    return float((v // s) * s)


def round_to_tick(price: float, tick: float) -> float:
    """Round a price to the nearest tick size."""
    if not tick or tick <= 0:
        return float(price)
    p, t = Decimal(str(price)), Decimal(str(tick))
    return float((p / t).quantize(Decimal(1), rounding=ROUND_HALF_UP) * t)
