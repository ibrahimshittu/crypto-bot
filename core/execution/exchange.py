"""Exchange abstraction Protocol that the whole system depends on instead of pybit directly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

Category = Literal["spot", "linear", "inverse", "option"]
Side = Literal["Buy", "Sell"]
OrderType = Literal["Market", "Limit"]


@dataclass(frozen=True)
class Instrument:
    symbol: str
    category: Category
    base_coin: str
    quote_coin: str
    min_order_qty: float
    qty_step: float
    min_order_notional: float = 0.0
    max_leverage: float = 1.0
    tick_size: float = 0.0


@dataclass(frozen=True)
class Ticker:
    symbol: str
    category: Category
    last_price: float
    bid: float
    ask: float
    turnover_24h: float
    volume_24h: float
    price_24h_pct: float = 0.0
    funding_rate: float = 0.0       # per-interval fraction (perps)

    @property
    def spread_bps(self) -> float:
        mid = (self.bid + self.ask) / 2.0
        return (self.ask - self.bid) / mid * 10_000.0 if mid > 0 else 0.0


@dataclass(frozen=True)
class OrderBook:
    symbol: str
    bids: list[tuple[float, float]]  # (price, size), best first
    asks: list[tuple[float, float]]

    def depth_notional_within(self, pct: float = 0.01) -> float:
        """Sum of resting notional within `pct` of mid (both sides)."""
        if not self.bids or not self.asks:
            return 0.0
        mid = (self.bids[0][0] + self.asks[0][0]) / 2.0
        lo, hi = mid * (1 - pct), mid * (1 + pct)
        bid_n = sum(p * s for p, s in self.bids if p >= lo)
        ask_n = sum(p * s for p, s in self.asks if p <= hi)
        return bid_n + ask_n


@dataclass(frozen=True)
class Kline:
    start_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    turnover: float = 0.0


@dataclass(frozen=True)
class Balance:
    total_equity: float             # quote ccy (USDT)
    available: float
    coin_balances: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Position:
    symbol: str
    category: Category
    side: Side
    size: float                     # base units, always positive
    entry_price: float
    leverage: float
    unrealized_pnl: float = 0.0

    @property
    def signed_size(self) -> float:
        return self.size if self.side == "Buy" else -self.size


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    category: Category
    side: Side
    order_type: OrderType
    qty: float
    price: float | None = None
    leverage: float | None = None
    reduce_only: bool = False
    take_profit: float | None = None
    stop_loss: float | None = None
    order_link_id: str | None = None
    strategy_id: str = ""


@dataclass(frozen=True)
class OrderResult:
    ok: bool
    order_id: str | None
    symbol: str
    filled_qty: float = 0.0
    avg_price: float = 0.0
    status: str = ""
    error: str = ""


@runtime_checkable
class ExchangeClient(Protocol):
    """Async exchange interface. PaperExchange and BybitClient both implement this."""

    env: str

    async def get_instruments(self, category: Category) -> list[Instrument]: ...
    async def get_kline(
        self, symbol: str, category: Category, interval: str = "60", limit: int = 200
    ) -> list[Kline]: ...
    async def get_ticker(self, symbol: str, category: Category) -> Ticker: ...
    async def get_tickers(self, category: Category) -> list[Ticker]: ...
    async def get_orderbook(self, symbol: str, category: Category, depth: int = 50) -> OrderBook: ...
    async def get_balance(self) -> Balance: ...
    async def get_positions(self, category: Category) -> list[Position]: ...
    async def set_leverage(self, symbol: str, category: Category, leverage: float) -> bool: ...
    async def place_order(self, req: OrderRequest) -> OrderResult: ...
    async def cancel_all(self, symbol: str, category: Category) -> bool: ...
