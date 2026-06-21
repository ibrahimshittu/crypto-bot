"""OHLCV persistence + deep historical backtest.

Klines fetched each cycle are persisted to the `ohlcv` (Timescale) hypertable so history
accumulates across runs, enabling longer-horizon, cross-regime validation than the ~500
bars an exchange returns on demand.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

import pandas as pd

from core.config import Settings, get_settings
from core.execution.exchange import Kline
from core.strategies import build_strategy
from core.validation.gate import GateResult, validate_strategy


class OhlcvStore(Protocol):
    async def save(self, symbol: str, category: str, interval: str, klines: list[Kline]) -> None: ...
    async def load(self, symbol: str, category: str, interval: str, limit: int = 2000) -> list[Kline]: ...


class InMemoryOhlcvStore:
    """Test/dev store keyed by (symbol, category, interval), deduped by bar start time."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str, str], dict[int, Kline]] = {}

    async def save(self, symbol: str, category: str, interval: str, klines: list[Kline]) -> None:
        bucket = self._data.setdefault((symbol, category, interval), {})
        for k in klines:
            bucket[k.start_ms] = k

    async def load(self, symbol: str, category: str, interval: str, limit: int = 2000) -> list[Kline]:
        bucket = self._data.get((symbol, category, interval), {})
        return [bucket[t] for t in sorted(bucket)][-limit:]


class PostgresOhlcvStore:
    """TimescaleDB-backed store (upsert into the `ohlcv` hypertable)."""

    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()

    async def save(self, symbol: str, category: str, interval: str, klines: list[Kline]) -> None:
        if not klines:
            return
        from data.db.connection import get_pg_pool

        rows = [
            (datetime.fromtimestamp(k.start_ms / 1000, tz=timezone.utc), symbol, category, interval,
             k.open, k.high, k.low, k.close, k.volume, k.turnover)
            for k in klines
        ]
        pool = await get_pg_pool(self.s)
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO ohlcv (time, symbol, category, interval, open, high, low, close, volume, turnover)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (symbol, category, interval, time) DO NOTHING
                """,
                rows,
            )

    async def load(self, symbol: str, category: str, interval: str, limit: int = 2000) -> list[Kline]:
        from data.db.connection import get_pg_pool

        pool = await get_pg_pool(self.s)
        async with pool.acquire() as conn:
            recs = await conn.fetch(
                "SELECT time, open, high, low, close, volume, turnover FROM ohlcv "
                "WHERE symbol=$1 AND category=$2 AND interval=$3 ORDER BY time DESC LIMIT $4",
                symbol, category, interval, limit,
            )
        recs = list(reversed(recs))
        return [
            Kline(int(r["time"].timestamp() * 1000), r["open"], r["high"], r["low"],
                  r["close"], r["volume"], r["turnover"] or 0.0)
            for r in recs
        ]


async def backtest_history(
    store: OhlcvStore, strategy_id: str, symbol: str, *,
    category: str = "linear", interval: str = "60", limit: int = 2000, n_trials: int = 50,
) -> GateResult | None:
    """Load stored history and validate the strategy over it (deep, cross-regime backtest)."""
    klines = await store.load(symbol, category, interval, limit)
    if len(klines) < 300:
        return None
    df = pd.DataFrame({
        "open": [k.open for k in klines], "high": [k.high for k in klines],
        "low": [k.low for k in klines], "close": [k.close for k in klines],
        "volume": [k.volume for k in klines],
    })
    positions = build_strategy(strategy_id).positions(df).to_numpy()
    returns = df["close"].pct_change().fillna(0.0).to_numpy()
    return validate_strategy(returns, positions, interval_minutes=60, n_trials=n_trials)
