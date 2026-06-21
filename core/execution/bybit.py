"""Bybit V5 client implementing ExchangeClient via the official `pybit` SDK."""

from __future__ import annotations

import asyncio
from typing import Any

from core.config import Settings, TradingEnv, get_settings
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


class BybitClient:
    """Thin async wrapper over pybit.unified_trading.HTTP."""

    def __init__(self, settings: Settings | None = None):
        self.s = settings or get_settings()
        self.env = self.s.trading_env.value
        from pybit.unified_trading import HTTP

        kwargs: dict[str, Any] = {
            "api_key": self.s.bybit_api_key,
            "api_secret": self.s.bybit_api_secret,
            "timeout": 30,
            "max_retries": 3,
        }
        if self.s.trading_env == TradingEnv.DEMO:
            kwargs["demo"] = True
        elif self.s.trading_env == TradingEnv.TESTNET:
            kwargs["testnet"] = True
        self._http = HTTP(**kwargs)

    async def _call(self, fn, /, **kwargs) -> dict:
        resp = await asyncio.to_thread(fn, **kwargs)
        if isinstance(resp, dict) and resp.get("retCode", 0) != 0:
            raise RuntimeError(f"Bybit error {resp.get('retCode')}: {resp.get('retMsg')}")
        return resp

    async def get_instruments(self, category: Category) -> list[Instrument]:
        out: list[Instrument] = []
        cursor: str | None = None
        while True:
            kwargs: dict[str, Any] = {"category": category, "limit": 1000}
            if cursor:
                kwargs["cursor"] = cursor
            resp = await self._call(self._http.get_instruments_info, **kwargs)
            result = resp["result"]
            for it in result["list"]:
                lot = it.get("lotSizeFilter", {})
                lev = it.get("leverageFilter", {})
                out.append(
                    Instrument(
                        symbol=it["symbol"],
                        category=category,
                        base_coin=it.get("baseCoin", ""),
                        quote_coin=it.get("quoteCoin", ""),
                        min_order_qty=float(lot.get("minOrderQty", 0) or 0),
                        qty_step=float(lot.get("qtyStep", lot.get("basePrecision", 0)) or 0),
                        min_order_notional=float(lot.get("minNotionalValue", 0) or 0),
                        max_leverage=float(lev.get("maxLeverage", 1) or 1),
                        tick_size=float(it.get("priceFilter", {}).get("tickSize", 0) or 0),
                    )
                )
            cursor = result.get("nextPageCursor") or None
            if not cursor:
                break
        return out

    async def get_kline(
        self, symbol: str, category: Category, interval: str = "60", limit: int = 200
    ) -> list[Kline]:
        resp = await self._call(
            self._http.get_kline, category=category, symbol=symbol,
            interval=interval, limit=limit,
        )
        rows = resp["result"]["list"]
        out = [
            Kline(
                start_ms=int(r[0]), open=float(r[1]), high=float(r[2]),
                low=float(r[3]), close=float(r[4]), volume=float(r[5]),
                turnover=float(r[6]) if len(r) > 6 else 0.0,
            )
            for r in rows
        ]
        out.reverse()
        return out

    def _ticker_from_raw(self, t: dict, category: Category) -> Ticker:
        bid = float(t.get("bid1Price", 0) or 0)
        ask = float(t.get("ask1Price", 0) or 0)
        return Ticker(
            symbol=t["symbol"],
            category=category,
            last_price=float(t.get("lastPrice", 0) or 0),
            bid=bid,
            ask=ask,
            turnover_24h=float(t.get("turnover24h", 0) or 0),
            volume_24h=float(t.get("volume24h", 0) or 0),
            price_24h_pct=float(t.get("price24hPcnt", 0) or 0) * 100.0,
            funding_rate=float(t.get("fundingRate", 0) or 0),
        )

    async def get_ticker(self, symbol: str, category: Category) -> Ticker:
        resp = await self._call(self._http.get_tickers, category=category, symbol=symbol)
        return self._ticker_from_raw(resp["result"]["list"][0], category)

    async def get_tickers(self, category: Category) -> list[Ticker]:
        resp = await self._call(self._http.get_tickers, category=category)
        return [self._ticker_from_raw(t, category) for t in resp["result"]["list"]]

    async def get_orderbook(self, symbol: str, category: Category, depth: int = 50) -> OrderBook:
        resp = await self._call(
            self._http.get_orderbook, category=category, symbol=symbol, limit=depth
        )
        r = resp["result"]
        return OrderBook(
            symbol=symbol,
            bids=[(float(p), float(s)) for p, s in r.get("b", [])],
            asks=[(float(p), float(s)) for p, s in r.get("a", [])],
        )

    async def get_balance(self) -> Balance:
        resp = await self._call(self._http.get_wallet_balance, accountType="UNIFIED")
        acct = resp["result"]["list"][0]
        coins = {c["coin"]: float(c.get("walletBalance", 0) or 0) for c in acct.get("coin", [])}
        return Balance(
            total_equity=float(acct.get("totalEquity", 0) or 0),
            available=float(acct.get("totalAvailableBalance", 0) or 0),
            coin_balances=coins,
        )

    async def get_positions(self, category: Category) -> list[Position]:
        resp = await self._call(
            self._http.get_positions, category=category, settleCoin="USDT"
        )
        out: list[Position] = []
        for p in resp["result"]["list"]:
            size = float(p.get("size", 0) or 0)
            if size == 0:
                continue
            out.append(
                Position(
                    symbol=p["symbol"],
                    category=category,
                    side=p.get("side", "Buy"),
                    size=size,
                    entry_price=float(p.get("avgPrice", 0) or 0),
                    leverage=float(p.get("leverage", 1) or 1),
                    unrealized_pnl=float(p.get("unrealisedPnl", 0) or 0),
                )
            )
        return out

    async def set_leverage(self, symbol: str, category: Category, leverage: float) -> bool:
        """Set buy/sell leverage on a perp symbol; 'not modified' (110043) is a no-op success."""
        if category not in ("linear", "inverse"):
            return True
        lev = str(leverage)
        try:
            await self._call(
                self._http.set_leverage, category=category, symbol=symbol,
                buyLeverage=lev, sellLeverage=lev,
            )
        except RuntimeError as e:
            if "110043" in str(e) or "not modified" in str(e).lower():
                return True
            raise
        return True

    async def place_order(self, req: OrderRequest) -> OrderResult:
        params: dict[str, Any] = {
            "category": req.category,
            "symbol": req.symbol,
            "side": req.side,
            "orderType": req.order_type,
            "qty": str(req.qty),
        }
        if req.price is not None:
            params["price"] = str(req.price)
        if req.reduce_only:
            params["reduceOnly"] = True
        if req.take_profit is not None:
            params["takeProfit"] = str(req.take_profit)
        if req.stop_loss is not None:
            params["stopLoss"] = str(req.stop_loss)
        if req.order_link_id:
            params["orderLinkId"] = req.order_link_id
        try:
            resp = await self._call(self._http.place_order, **params)
        except RuntimeError as e:
            return OrderResult(ok=False, order_id=None, symbol=req.symbol, error=str(e))
        oid = resp["result"].get("orderId")
        return OrderResult(ok=True, order_id=oid, symbol=req.symbol, status="Submitted")

    async def cancel_all(self, symbol: str, category: Category) -> bool:
        await self._call(self._http.cancel_all_orders, category=category, symbol=symbol)
        return True


def make_exchange(settings: Settings | None = None):
    """Factory: PaperExchange for paper/tests, BybitClient otherwise."""
    s = settings or get_settings()
    return BybitClient(s)
