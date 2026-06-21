"""Shared application state: the trading engine the API controls and observes."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field

from agents.deps import TradingDeps
from agents.orchestrator import Orchestrator
from agents.schemas import CycleDecision

_RUNNING_KEY = "cryptobot:engine:running"
_CYCLES_KEY = "cryptobot:engine:cycles"
_MAX_PERSISTED_CYCLES = 200


@dataclass
class EngineState:
    deps: TradingDeps
    cycle_seconds: float = 60.0
    running: bool = False
    enable_persistence: bool = False
    _task: asyncio.Task | None = None
    history: deque[CycleDecision] = field(default_factory=lambda: deque(maxlen=200))

    in_progress: bool = False
    cycles_completed: int = 0
    last_started: float | None = None
    last_finished: float | None = None
    last_error: str | None = None

    def __post_init__(self) -> None:
        self.orchestrator = Orchestrator(self.deps)

    # ── one cycle ───────────────────────────────────────────────────────────────
    async def run_once(self) -> CycleDecision:
        self.in_progress = True
        self.last_started = time.time()
        n = self.cycles_completed + 1
        print(f"[engine] ▶ cycle #{n} starting (scanning market)…", flush=True)
        from core.observability import span

        try:
            with span("trading cycle", cycle=n) as sp:
                decision = await self.orchestrator.run_cycle()
                if sp is not None:
                    sp.set_attributes({
                        "candidates": decision.n_candidates,
                        "signals": decision.n_signals,
                        "orders": decision.n_orders,
                        "session": decision.session_label,
                        "notes": decision.notes,
                    })
            self.history.append(decision)
            self.cycles_completed = n
            self.last_error = None
            self._fire(self._persist_cycle(decision))
            print(
                f"[engine] ✓ cycle #{n} done: {decision.n_candidates} candidates, "
                f"{decision.n_signals} signals, {decision.n_orders} orders "
                f"({decision.session_label})",
                flush=True,
            )
            return decision
        finally:
            self.in_progress = False
            self.last_finished = time.time()

    async def _loop(self) -> None:
        while self.running:
            try:
                await self.run_once()
            except Exception as e:  # never let one bad cycle kill the loop
                self.last_error = str(e)
                print(f"[engine] ✗ cycle error: {e}", flush=True)
                self.history.append(
                    CycleDecision(
                        session_label="error", liquidity_score=0.0, n_candidates=0,
                        n_signals=0, n_orders=0, n_pending_approval=0,
                        notes=[f"cycle error: {e}"],
                    )
                )
            await asyncio.sleep(self.cycle_seconds)

    # ── lifecycle ───────────────────────────────────────────────────────────────
    def start(self, *, persist: bool = True) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())
        if persist:
            self._fire(self._persist_running(True))
        print(f"[engine] loop started (every {self.cycle_seconds:.0f}s)", flush=True)

    async def stop(self) -> None:
        """User-initiated stop — persists 'stopped' so it won't auto-resume."""
        self.running = False
        await self._persist_running(False)
        await self._cancel_task()
        print("[engine] loop stopped (by user)", flush=True)

    async def shutdown(self) -> None:
        """Process shutdown — cancel the loop but KEEP the desired state so the next
        process resumes it. Called from the FastAPI lifespan on exit."""
        self.running = False
        await self._cancel_task()

    async def _cancel_task(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def restore(self) -> None:
        """On startup: reload recent cycle history + resume if the user had it running."""
        if not self.enable_persistence:
            return
        self.history.extend(await self._load_cycles())
        self.cycles_completed = len(self.history)
        if await self._load_running():
            print("[engine] resuming (was running before restart)", flush=True)
            self.start(persist=False)

    # ── status ──────────────────────────────────────────────────────────────────
    def status(self) -> dict:
        now = time.time()
        last = self.history[-1] if self.history else None
        next_in = None
        if self.running and not self.in_progress and self.last_finished is not None:
            next_in = round(max(0.0, self.cycle_seconds - (now - self.last_finished)), 1)
        phase = (
            "running a cycle now" if self.in_progress
            else "idle — waiting for next cycle" if self.running
            else "stopped"
        )
        return {
            "running": self.running,
            "phase": phase,
            "in_progress": self.in_progress,
            "cycle_seconds": self.cycle_seconds,
            "cycles_completed": self.cycles_completed,
            "history_size": len(self.history),
            "seconds_since_last_cycle": (
                round(now - self.last_finished, 1) if self.last_finished else None
            ),
            "next_cycle_in_seconds": next_in,
            "persistence": self.enable_persistence,
            "last_error": self.last_error,
            "last_decision": last.model_dump() if last else None,
        }

    # ── Redis persistence (all guarded; degrade to in-memory) ───────────────────
    def _fire(self, coro) -> None:
        """Schedule a fire-and-forget coroutine; close it if there's no running loop."""
        if not self.enable_persistence:
            coro.close()
            return
        try:
            asyncio.create_task(coro)
        except RuntimeError:
            coro.close()

    async def _persist_running(self, running: bool) -> None:
        if not self.enable_persistence:
            return
        try:
            from data.db import get_redis

            await get_redis().set(_RUNNING_KEY, "1" if running else "0")
        except Exception:
            pass

    async def _persist_cycle(self, decision: CycleDecision) -> None:
        try:
            from data.db import get_redis

            r = get_redis()
            await r.rpush(_CYCLES_KEY, decision.model_dump_json())
            await r.ltrim(_CYCLES_KEY, -_MAX_PERSISTED_CYCLES, -1)
        except Exception:
            pass

    async def _load_cycles(self) -> list[CycleDecision]:
        try:
            from data.db import get_redis

            raw = await get_redis().lrange(_CYCLES_KEY, -_MAX_PERSISTED_CYCLES, -1)
            return [CycleDecision.model_validate_json(x) for x in raw]
        except Exception:
            return []

    async def _load_running(self) -> bool:
        try:
            from data.db import get_redis

            return (await get_redis().get(_RUNNING_KEY)) == "1"
        except Exception:
            return False
