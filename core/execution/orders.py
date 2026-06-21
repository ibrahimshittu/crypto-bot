"""Order approval workflow — the phased-rollout safety gate."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum

from core.config import Settings, TradingEnv, get_settings
from core.execution.exchange import ExchangeClient, OrderRequest, OrderResult


class ApprovalStatus(str, Enum):
    PENDING = "pending_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class OrderTicket:
    id: int
    request: OrderRequest
    status: ApprovalStatus
    result: OrderResult | None = None
    note: str = ""
    meta: dict = field(default_factory=dict)


class OrderWorkflow:
    """Routes orders through approval based on env + per-strategy auto whitelist."""

    def __init__(
        self,
        exchange: ExchangeClient,
        settings: Settings | None = None,
        auto_whitelist: set[str] | None = None,
    ):
        self.exchange = exchange
        self.s = settings or get_settings()
        self.auto_whitelist = auto_whitelist or set()
        self._tickets: dict[int, OrderTicket] = {}
        self._ids = itertools.count(1)

    def _auto_submit_allowed(self, req: OrderRequest) -> bool:
        if self.s.trading_env != TradingEnv.LIVE:
            return True
        return req.strategy_id in self.auto_whitelist

    async def submit(self, req: OrderRequest) -> OrderTicket:
        """Entry point for the trading loop. Returns a ticket; may or may not be filled."""
        ticket = OrderTicket(id=next(self._ids), request=req, status=ApprovalStatus.PENDING)
        self._tickets[ticket.id] = ticket

        if self._auto_submit_allowed(req):
            await self._execute(ticket)
        else:
            ticket.note = "awaiting human approval (live, non-whitelisted strategy)"
        return ticket

    async def approve(self, ticket_id: int) -> OrderTicket:
        """Human approves a pending live order → execute it."""
        ticket = self._tickets[ticket_id]
        if ticket.status != ApprovalStatus.PENDING:
            return ticket
        ticket.status = ApprovalStatus.APPROVED
        await self._execute(ticket)
        return ticket

    def reject(self, ticket_id: int, reason: str = "") -> OrderTicket:
        ticket = self._tickets[ticket_id]
        ticket.status = ApprovalStatus.REJECTED
        ticket.note = reason or "rejected by operator"
        return ticket

    async def _execute(self, ticket: OrderTicket) -> None:
        result = await self.exchange.place_order(ticket.request)
        ticket.result = result
        ticket.status = ApprovalStatus.SUBMITTED if result.ok else ApprovalStatus.FAILED
        if not result.ok:
            ticket.note = result.error

    def pending(self) -> list[OrderTicket]:
        return [t for t in self._tickets.values() if t.status == ApprovalStatus.PENDING]

    def all_tickets(self) -> list[OrderTicket]:
        return list(self._tickets.values())
