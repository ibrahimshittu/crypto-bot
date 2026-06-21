"""Bybit DEMO connectivity smoke test."""

import asyncio

from core.config import TradingEnv, get_settings
from core.execution.bybit import BybitClient
from core.execution.exchange import OrderRequest


async def main() -> None:
    s = get_settings()
    print(f"env={s.trading_env.value} host={s.bybit_rest_host}")
    if s.trading_env == TradingEnv.LIVE:
        raise SystemExit("Refusing to run the smoke test against LIVE. Set TRADING_ENV=demo.")
    if not s.bybit_api_key:
        raise SystemExit("No BYBIT_API_KEY set — fill in .env (demo keys).")

    ex = BybitClient(s)

    bal = await ex.get_balance()
    print(f"✓ balance: equity={bal.total_equity:.2f} available={bal.available:.2f}")

    instruments = await ex.get_instruments("linear")
    print(f"✓ instruments(linear): {len(instruments)}")

    ticker = await ex.get_ticker("BTCUSDT", "linear")
    print(f"✓ BTCUSDT last={ticker.last_price} spread={ticker.spread_bps:.2f}bps "
          f"funding={ticker.funding_rate}")

    klines = await ex.get_kline("BTCUSDT", "linear", interval="60", limit=10)
    print(f"✓ klines: {len(klines)} bars, latest close={klines[-1].close if klines else 'n/a'}")

    ob = await ex.get_orderbook("BTCUSDT", "linear", depth=25)
    print(f"✓ orderbook: ±1% depth ≈ ${ob.depth_notional_within(0.01):,.0f}")

    inst = next((i for i in instruments if i.symbol == "BTCUSDT"), None)
    qty = max(inst.min_order_qty, 0.001) if inst else 0.001
    res = await ex.place_order(
        OrderRequest("BTCUSDT", "linear", "Buy", "Market", qty=qty, strategy_id="smoke")
    )
    print(f"{'✓' if res.ok else '✗'} demo order: ok={res.ok} id={res.order_id} err={res.error}")

    print("\nAll demo connectivity checks completed.")


if __name__ == "__main__":
    asyncio.run(main())
