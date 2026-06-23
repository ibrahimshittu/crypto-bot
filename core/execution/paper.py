"""In-memory paper exchange implementing ExchangeClient with no network."""

from __future__ import annotations

import itertools

from core.execution.exchange import (
    Balance,
    Category,
    Instrument,
    Kline,
    OrderBook,
    OrderRequest,
    OrderResult,
    Position,
    Ticker,
)


class PaperExchange:
    env = "paper"

    def __init__(self, starting_equity: float = 1000.0, slippage: float = 0.0005):
        self._equity = starting_equity
        self._available = starting_equity
        self._slippage = slippage
        self._instruments: dict[tuple[str, str], Instrument] = {}
        self._tickers: dict[str, Ticker] = {}
        self._books: dict[str, OrderBook] = {}
        self._positions: dict[str, Position] = {}
        self.orders: list[OrderRequest] = []
        self._klines: dict[str, list[Kline]] = {}
        self._funding: dict[str, list[float]] = {}
        self._oi: dict[str, list[float]] = {}
        self._ids = itertools.count(1)

    def add_instrument(self, inst: Instrument) -> None:
        self._instruments[(inst.symbol, inst.category)] = inst

    def set_ticker(self, t: Ticker) -> None:
        self._tickers[t.symbol] = t

    def set_orderbook(self, ob: OrderBook) -> None:
        self._books[ob.symbol] = ob

    def set_klines(self, symbol: str, klines: list[Kline]) -> None:
        self._klines[symbol] = klines

    def set_funding_history(self, symbol: str, rates: list[float]) -> None:
        self._funding[symbol] = rates

    def set_open_interest(self, symbol: str, oi: list[float]) -> None:
        self._oi[symbol] = oi

    async def get_instruments(self, category: Category) -> list[Instrument]:
        return [i for (s, c), i in self._instruments.items() if c == category]

    async def get_kline(
        self, symbol: str, category: Category, interval: str = "60", limit: int = 200
    ) -> list[Kline]:
        return self._klines.get(symbol, [])[-limit:]

    async def get_ticker(self, symbol: str, category: Category) -> Ticker:
        return self._tickers[symbol]

    async def get_tickers(self, category: Category) -> list[Ticker]:
        return [t for t in self._tickers.values() if t.category == category]

    async def get_orderbook(self, symbol: str, category: Category, depth: int = 50) -> OrderBook:
        return self._books.get(symbol, OrderBook(symbol=symbol, bids=[], asks=[]))

    async def get_funding_history(self, symbol: str, category: Category, limit: int = 50) -> list[float]:
        return self._funding.get(symbol, [])[-limit:]

    async def get_open_interest(
        self, symbol: str, category: Category, interval: str = "1h", limit: int = 50
    ) -> list[float]:
        return self._oi.get(symbol, [])[-limit:]

    async def get_balance(self) -> Balance:
        return Balance(total_equity=self._equity, available=self._available)

    async def get_positions(self, category: Category) -> list[Position]:
        return [p for p in self._positions.values() if p.category == category]

    async def set_leverage(self, symbol: str, category: Category, leverage: float) -> bool:
        return True

    async def place_order(self, req: OrderRequest) -> OrderResult:
        self.orders.append(req)
        ticker = self._tickers.get(req.symbol)
        if ticker is None:
            return OrderResult(ok=False, order_id=None, symbol=req.symbol, error="no ticker")

        ref = req.price if (req.order_type == "Limit" and req.price) else ticker.last_price
        slip = self._slippage if req.side == "Buy" else -self._slippage
        fill = ref * (1 + slip)

        existing = self._positions.get(req.symbol)
        signed = req.qty if req.side == "Buy" else -req.qty
        prev_signed = existing.signed_size if existing else 0.0
        new_signed = prev_signed + signed

        if abs(new_signed) < 1e-12:
            self._positions.pop(req.symbol, None)
        else:
            side = "Buy" if new_signed > 0 else "Sell"
            self._positions[req.symbol] = Position(
                symbol=req.symbol, category=req.category, side=side,
                size=abs(new_signed), entry_price=fill,
                leverage=req.leverage or 1.0,
            )

        return OrderResult(
            ok=True, order_id=str(next(self._ids)), symbol=req.symbol,
            filled_qty=req.qty, avg_price=fill, status="Filled",
        )

    async def cancel_all(self, symbol: str, category: Category) -> bool:
        return True
