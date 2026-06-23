"""Orchestrator — runs one full decision cycle."""

from __future__ import annotations

import dataclasses

from agents.deps import TradingDeps
from agents.reasoners import fetch_klines
from agents.schemas import CycleDecision
from core.analysis.edge import estimate_edge
from core.analysis.features import funding_trend, multiframe_confluence, oi_change_pct
from core.analysis.health import strategy_health
from core.observability import span
from core.risk.sizing import edge_scaled_size
from core.execution.exchange import OrderRequest
from core.execution.rounding import floor_to_step, round_to_tick
from core.validation.online import validate_recent
from core.risk.state import PortfolioState, Position


async def _enrich_candidate(deps: TradingDeps, cand, klines):
    """Attach multi-timeframe confluence and live derivative features (funding trend, OI)."""
    updates: dict = {}
    with span("analysis.enrich", symbol=cand.symbol, regime=cand.snapshot.regime):
        try:
            k4h = await deps.exchange.get_kline(cand.symbol, cand.category, interval="240", limit=200)
            k1d = await deps.exchange.get_kline(cand.symbol, cand.category, interval="D", limit=200)
            updates["mtf_confluence"] = multiframe_confluence(klines, k4h, k1d)["confluence"]
        except Exception:
            pass
        if cand.category in ("linear", "inverse"):
            try:
                fh = await deps.exchange.get_funding_history(cand.symbol, cand.category, limit=50)
                oi = await deps.exchange.get_open_interest(cand.symbol, cand.category, limit=50)
                updates["funding_trend"] = funding_trend(fh)
                updates["oi_change_pct"] = oi_change_pct(oi)
            except Exception:
                pass
    if not updates:
        return cand
    return dataclasses.replace(cand, snapshot=dataclasses.replace(cand.snapshot, **updates))


class Orchestrator:
    def __init__(self, deps: TradingDeps):
        self.deps = deps

    async def _portfolio(self) -> PortfolioState:
        bal = await self.deps.exchange.get_balance()
        positions = await self.deps.exchange.get_positions(self.deps.category)
        risk_positions = [
            Position(
                symbol=p.symbol, qty=p.signed_size, entry_price=p.entry_price,
                leverage=p.leverage,
            )
            for p in positions
        ]
        # start_of_day_equity should come from persisted state; fall back to equity.
        sod = getattr(self, "_sod_equity", None) or bal.total_equity
        return PortfolioState(
            equity=bal.total_equity, start_of_day_equity=sod, positions=risk_positions
        )

    def set_start_of_day_equity(self, equity: float) -> None:
        self._sod_equity = equity

    async def run_cycle(self) -> CycleDecision:
        d = self.deps
        session = d.clock.now()
        notes: list[str] = [f"session={session.label} liq={session.liquidity_score:.2f}"]

        from data.market.snapshots import build_universe_snapshots

        snapshots = await build_universe_snapshots(
            d.exchange, d.category, max_symbols=d.max_symbols
        )
        candidates = d.scanner.top(snapshots, n=d.max_candidates)
        notes.append(f"{len(snapshots)} scanned → {len(candidates)} candidates")

        instruments = {i.symbol: i for i in await d.exchange.get_instruments(d.category)}

        portfolio = await self._portfolio()
        if portfolio.daily_pnl_pct <= -abs(d.settings.daily_loss_halt_pct):
            notes.append(f"HALT: daily P&L {portfolio.daily_pnl_pct:.2f}% tripped breaker")
            return CycleDecision(
                session_label=session.label, liquidity_score=session.liquidity_score,
                n_candidates=len(candidates), n_signals=0, n_orders=0,
                n_pending_approval=0, notes=notes,
            )

        held = {p.symbol for p in portfolio.positions}
        n_signals = n_orders = 0
        for cand in candidates:
            if n_orders >= d.max_new_orders_per_cycle:
                notes.append(f"reached max {d.max_new_orders_per_cycle} new orders/cycle")
                break
            if cand.symbol in held:  # already in a position — don't pile on
                notes.append(f"{cand.symbol} skipped: already holding a position")
                continue

            klines = await fetch_klines(d.exchange, cand)
            if d.ohlcv_store is not None:
                try:
                    await d.ohlcv_store.save(cand.symbol, cand.category, "60", klines)
                except Exception:
                    pass
            cand = await _enrich_candidate(d, cand, klines)
            sentiment = await d.sentiment_reasoner.assess(cand.symbol)
            decision = await d.strategy_reasoner.decide(cand, klines, sentiment)
            if decision is None:
                continue
            if abs(decision.target_position) < 1e-9:  # LLM declined the trade
                notes.append(f"{cand.symbol} declined by strategy reasoner")
                continue
            if decision.strategy_id == "funding_carry_basis":  # needs delta-neutral two-leg path
                notes.append(f"{cand.symbol} skipped: carry needs delta-neutral execution")
                continue
            if strategy_health(await d.journal.recent_trades(200), decision.strategy_id,
                               min_trades=d.health_min_trades).benched:
                notes.append(f"{cand.symbol} skipped: {decision.strategy_id} benched (decaying edge)")
                continue
            if d.require_validation:
                with span("analysis.validate", symbol=cand.symbol, strategy=decision.strategy_id):
                    rv = validate_recent(decision.strategy_id, cand.symbol, klines,
                                         n_trials=d.validation_n_trials)
                if not rv.tradeable:
                    notes.append(f"{cand.symbol} skipped: failed recent validation ({rv.reason})")
                    continue
            n_signals += 1

            inst = instruments.get(cand.symbol)

            # The risk engine is the veto/sizing gate and enforces exchange minimums.
            ob = await d.exchange.get_orderbook(cand.symbol, cand.category, depth=50)
            risk = d.risk.evaluate(
                portfolio=portfolio,
                symbol=decision.symbol,
                side="Buy" if decision.target_position > 0 else "Sell",
                entry_price=decision.entry_price,
                stop_price=decision.stop_price,
                leverage=decision.leverage,
                depth_notional=ob.depth_notional_within(0.01),
                min_order_qty=inst.min_order_qty if inst else 0.0,
                min_order_notional=inst.min_order_notional if inst else 0.0,
            )
            if not risk.approved or risk.sizing is None:
                notes.append(f"{cand.symbol} vetoed: {'; '.join(risk.reasons)}")
                if risk.halt_trading:
                    break
                continue

            # Scale the risk-approved size by the strategy's estimated edge.
            edge = estimate_edge(klines, decision.strategy_id)
            sizing = edge_scaled_size(risk.sizing, edge.kelly_fraction)

            # Never order without a known lot step — we can't round qty safely.
            if inst is None:
                notes.append(f"{cand.symbol} skipped: no instrument spec (lot step unknown)")
                continue
            # Round qty to the lot step and prices to the tick size, or Bybit rejects it.
            qty = floor_to_step(sizing.qty, inst.qty_step)
            if inst.min_order_qty and qty < inst.min_order_qty:
                notes.append(
                    f"{cand.symbol} skipped: rounded qty {qty} < min {inst.min_order_qty}"
                )
                continue
            tick = inst.tick_size
            side = "Buy" if decision.target_position > 0 else "Sell"

            # Always set a take-profit. If the strategy/LLM omitted one, derive a 2:1 R:R
            # target from the entry and stop so no position is left open-ended.
            take_profit = decision.take_profit
            if take_profit is None:
                stop_dist = abs(decision.entry_price - decision.stop_price)
                take_profit = (decision.entry_price + 2 * stop_dist if side == "Buy"
                               else decision.entry_price - 2 * stop_dist)

            # Use the risk engine's ENFORCED (clamped) leverage, not the strategy's raw
            # proposal — this is the hard cap the LLM can't exceed.
            leverage = risk.leverage

            # Apply leverage on the symbol first — Bybit's max position size depends on it
            # (risk-limit tiers). Best-effort: a failure here shouldn't block the cycle.
            if cand.category in ("linear", "inverse"):
                try:
                    await d.exchange.set_leverage(cand.symbol, cand.category, leverage)
                except Exception as e:
                    notes.append(f"{cand.symbol} set_leverage failed: {e}")
                    continue

            # Order workflow is auto on demo, approval-gated on live.
            req = OrderRequest(
                symbol=decision.symbol,
                category=cand.category,
                side=side,
                order_type="Market",
                qty=qty,
                leverage=leverage,
                take_profit=round_to_tick(take_profit, tick),
                stop_loss=round_to_tick(decision.stop_price, tick),
                strategy_id=decision.strategy_id,
            )
            assert d.workflow is not None
            ticket = await d.workflow.submit(req)
            n_orders += 1
            notes.append(
                f"{cand.symbol} {decision.action} qty={req.qty} → {ticket.status.value}"
            )

        pending = len(d.workflow.pending()) if d.workflow else 0
        return CycleDecision(
            session_label=session.label,
            liquidity_score=session.liquidity_score,
            n_candidates=len(candidates),
            n_signals=n_signals,
            n_orders=n_orders,
            n_pending_approval=pending,
            notes=notes,
        )
