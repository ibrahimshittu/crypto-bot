"""Postgres-backed JournalStore — persists trades + lessons in the cloud DB."""

from __future__ import annotations

import json

from agents.schemas import Lesson
from core.config import Settings, get_settings
from data.db.connection import get_pg_pool
from memory.journal import JournalEntry


class PostgresJournal:
    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self.env = self.s.trading_env.value

    async def record_trade(self, entry: JournalEntry) -> None:
        pool = await get_pg_pool(self.s)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO trade_journal
                  (symbol, strategy, session_label, regime, thesis, entry_price,
                   exit_price, qty, pnl, pnl_pct, expected_slippage, realized_slippage, meta)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                """,
                entry.symbol, entry.strategy_id, entry.session_label, entry.regime,
                entry.thesis, entry.entry_price, entry.exit_price, entry.qty, entry.pnl,
                entry.pnl_pct, entry.expected_slippage, entry.realized_slippage,
                json.dumps(entry.meta),
            )

    async def recent_trades(self, limit: int = 100) -> list[JournalEntry]:
        pool = await get_pg_pool(self.s)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM trade_journal ORDER BY closed_at DESC LIMIT $1", limit
            )
        return [
            JournalEntry(
                symbol=r["symbol"], strategy_id=r["strategy"] or "",
                session_label=r["session_label"] or "", regime=r["regime"] or "",
                thesis=r["thesis"] or "", entry_price=r["entry_price"] or 0.0,
                exit_price=r["exit_price"] or 0.0, qty=r["qty"] or 0.0,
                pnl=r["pnl"] or 0.0, pnl_pct=r["pnl_pct"] or 0.0,
                expected_slippage=r["expected_slippage"] or 0.0,
                realized_slippage=r["realized_slippage"] or 0.0,
                meta=json.loads(r["meta"]) if r["meta"] else {},
            )
            for r in reversed(rows)
        ]

    async def add_lesson(self, lesson: Lesson) -> None:
        pool = await get_pg_pool(self.s)
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO lessons (scope, lesson, weight) VALUES ($1,$2,$3)",
                lesson.scope, lesson.lesson, lesson.weight,
            )

    async def lessons_for(self, scope: str | None = None, limit: int = 20) -> list[Lesson]:
        pool = await get_pg_pool(self.s)
        async with pool.acquire() as conn:
            if scope:
                rows = await conn.fetch(
                    "SELECT scope, lesson, weight FROM lessons WHERE scope ILIKE $1 "
                    "ORDER BY weight DESC LIMIT $2",
                    f"%{scope}%", limit,
                )
            else:
                rows = await conn.fetch(
                    "SELECT scope, lesson, weight FROM lessons ORDER BY weight DESC LIMIT $1",
                    limit,
                )
        return [Lesson(scope=r["scope"] or "", lesson=r["lesson"], weight=r["weight"]) for r in rows]
