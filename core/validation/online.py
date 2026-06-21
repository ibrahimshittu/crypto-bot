"""Cached recent-history validation: gate a strategy/symbol on a fresh CPCV + deflated-Sharpe check."""

from __future__ import annotations

import time
from dataclasses import dataclass

import pandas as pd

from core.execution.exchange import Kline
from core.strategies import build_strategy
from core.validation.gate import validate_strategy

_CACHE: dict[tuple[str, str], tuple[float, "RecentValidation"]] = {}


@dataclass(frozen=True)
class RecentValidation:
    tradeable: bool
    deflated_sharpe: float
    median_oos_sharpe: float
    reason: str


def _clear_cache() -> None:
    _CACHE.clear()


def _frame(klines: list[Kline]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [k.open for k in klines],
            "high": [k.high for k in klines],
            "low": [k.low for k in klines],
            "close": [k.close for k in klines],
            "volume": [k.volume for k in klines],
        }
    )


def validate_recent(
    strategy_id: str,
    symbol: str,
    klines: list[Kline],
    *,
    n_trials: int = 25,
    ttl_seconds: float = 3600.0,
    sharpe_floor: float = 0.3,
    dsr_floor: float = 0.9,
    now: float | None = None,
) -> RecentValidation:
    """Run the validation gate on the strategy's positions over `klines`, cached per
    (strategy_id, symbol) for `ttl_seconds`. Strategies with no price-based signal
    (e.g. funding_carry_basis) are treated as not-tradeable here."""
    now = time.time() if now is None else now
    key = (strategy_id, symbol)
    cached = _CACHE.get(key)
    if cached is not None and now - cached[0] < ttl_seconds:
        return cached[1]

    if len(klines) < 300:
        result = RecentValidation(False, 0.0, 0.0, "insufficient history")
    else:
        df = _frame(klines)
        positions = build_strategy(strategy_id).positions(df).to_numpy()
        returns = df["close"].pct_change().fillna(0.0).to_numpy()
        gate = validate_strategy(
            returns, positions, interval_minutes=60, n_trials=n_trials,
            sharpe_floor=sharpe_floor, dsr_floor=dsr_floor,
        )
        result = RecentValidation(
            tradeable=gate.passed,
            deflated_sharpe=gate.deflated_sharpe,
            median_oos_sharpe=gate.median_oos_sharpe,
            reason="; ".join(gate.reasons),
        )

    _CACHE[key] = (now, result)
    return result
