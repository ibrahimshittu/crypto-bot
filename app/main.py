"""FastAPI control plane: REST + WebSocket over the persistent trading loop."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from agents.deps import TradingDeps
from app.state import EngineState
from core.config import Settings, TradingEnv, get_settings
from core.execution.exchange import ExchangeClient
from core.execution.paper import PaperExchange


class ApproveBody(BaseModel):
    ticket_id: int


def build_trading_deps(settings: Settings) -> TradingDeps:
    """Construct TradingDeps, wiring the optional reasoners by available credentials."""
    deps = TradingDeps(exchange=_default_exchange(settings), settings=settings)
    deps.max_symbols = settings.universe_max_symbols or None  # 0 = scan the entire universe
    deps.max_candidates = settings.max_candidates
    deps.max_new_orders_per_cycle = settings.max_new_orders_per_cycle
    if settings.database_url:
        from data.db.ohlcv import PostgresOhlcvStore

        deps.ohlcv_store = PostgresOhlcvStore(settings)

    if settings.exa_api_key:
        try:
            from agents.reasoners import ExaSentimentReasoner

            deps.sentiment_reasoner = ExaSentimentReasoner(settings)
        except Exception:
            pass

    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required — the strategy reasoner is LLM-first.")
    from agents.llm import LLMStrategyReasoner

    deps.strategy_reasoner = LLMStrategyReasoner(settings)
    return deps


def _default_exchange(settings: Settings) -> ExchangeClient:
    """Pick a safe default exchange. Paper unless explicitly configured for Bybit."""
    if settings.bybit_api_key and settings.trading_env in (TradingEnv.DEMO, TradingEnv.TESTNET, TradingEnv.LIVE):
        try:
            from core.execution.bybit import BybitClient

            return BybitClient(settings)
        except Exception:
            return PaperExchange()
    return PaperExchange()


def create_app(engine: EngineState | None = None, *, auto_start: bool = False) -> FastAPI:
    settings = get_settings()
    if engine is None:
        engine = EngineState(
            deps=build_trading_deps(settings),
            cycle_seconds=settings.cycle_seconds,
            enable_persistence=True,   # mirror running-state + cycles to Redis
        )

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.engine = engine
        await engine.restore()         # resume from Redis if it was running before
        if auto_start:
            engine.start()
        yield
        await engine.shutdown()        # process exit — keep desired state for next start

    app = FastAPI(title="crypto_bot control plane", lifespan=lifespan)
    app.state.engine = engine

    # No-op if Logfire isn't configured.
    from core.observability import configure_observability

    configure_observability(app, settings)

    # ── REST ──────────────────────────────────────────────────────────────────
    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "env": settings.trading_env.value, "running": engine.running}

    @app.get("/engine/status")
    async def engine_status() -> dict:
        """Live view of what the engine is doing right now: running/idle, whether a cycle
        is in progress, how many it's completed, seconds to the next one, and last result."""
        return engine.status()

    @app.get("/health/deps")
    async def health_deps() -> dict:
        """Ping the cloud datastores (Postgres + Redis). Use this right after deploy to
        confirm DATABASE_URL / REDIS_URL are wired correctly."""
        from data.db import healthcheck

        return await healthcheck(settings)

    @app.post("/engine/start")
    async def start() -> dict:
        engine.start()
        return {"running": True, "cycle_seconds": engine.cycle_seconds}

    @app.post("/engine/stop")
    async def stop() -> dict:
        await engine.stop()
        return {"running": False}

    @app.post("/engine/run-once")
    async def run_once() -> dict:
        decision = await engine.run_once()
        return decision.model_dump()

    @app.get("/cycles")
    async def cycles(limit: int = 20) -> list[dict]:
        return [c.model_dump() for c in list(engine.history)[-limit:]]

    @app.get("/balance")
    async def balance() -> dict:
        bal = await engine.deps.exchange.get_balance()
        return {"equity": bal.total_equity, "available": bal.available}

    @app.get("/positions")
    async def positions() -> list[dict]:
        ps = await engine.deps.exchange.get_positions(engine.deps.category)
        return [
            {"symbol": p.symbol, "side": p.side, "size": p.size,
             "entry": p.entry_price, "lev": p.leverage, "uPnL": p.unrealized_pnl}
            for p in ps
        ]

    @app.get("/orders/pending")
    async def pending_orders() -> list[dict]:
        wf = engine.deps.workflow
        assert wf is not None
        return [
            {"id": t.id, "symbol": t.request.symbol, "side": t.request.side,
             "qty": t.request.qty, "strategy": t.request.strategy_id, "note": t.note}
            for t in wf.pending()
        ]

    @app.post("/orders/approve")
    async def approve(body: ApproveBody) -> dict:
        wf = engine.deps.workflow
        assert wf is not None
        if body.ticket_id not in {t.id for t in wf.all_tickets()}:
            raise HTTPException(404, "ticket not found")
        ticket = await wf.approve(body.ticket_id)
        return {"id": ticket.id, "status": ticket.status.value, "note": ticket.note}

    @app.post("/orders/reject")
    async def reject(body: ApproveBody) -> dict:
        wf = engine.deps.workflow
        assert wf is not None
        ticket = wf.reject(body.ticket_id)
        return {"id": ticket.id, "status": ticket.status.value}

    @app.post("/research/{symbol}")
    async def deep_research(symbol: str) -> dict:
        """On-demand Exa deep-research dive for one symbol (slow/high-compute; not run in
        the scan loop). Returns the synthesized report, or a note if Exa isn't configured."""
        from data.news.exa import ExaClient

        client = ExaClient(settings.exa_api_key)
        if not client.enabled:
            raise HTTPException(400, "EXA_API_KEY not configured")
        report = await client.deep_research(symbol.upper())
        return {"symbol": symbol.upper(), "report": report}

    # ── WebSocket: stream cycle decisions ───────────────────────────────────────
    @app.websocket("/ws/cycles")
    async def ws_cycles(ws: WebSocket) -> None:
        await ws.accept()
        last = 0
        try:
            while True:
                hist = list(engine.history)
                if len(hist) > last:
                    for c in hist[last:]:
                        await ws.send_text(json.dumps(c.model_dump()))
                    last = len(hist)
                await asyncio.sleep(1.0)
        except WebSocketDisconnect:
            return

    return app


# Module-level app for `uvicorn app.main:app`. Set AUTO_START=true in the cloud to launch
# the trading loop on boot; left off by default for safety.
app = create_app(auto_start=os.getenv("AUTO_START", "false").lower() == "true")
