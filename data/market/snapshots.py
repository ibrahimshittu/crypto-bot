"""Build InstrumentSnapshot objects (scanner input) from live exchange data."""

from __future__ import annotations

import asyncio

from core.execution.exchange import Category, ExchangeClient, Ticker
from core.screener.scanner import InstrumentSnapshot
from data.market import indicators as ind


async def build_snapshot(
    exchange: ExchangeClient,
    ticker: Ticker,
    *,
    interval: str = "60",
    kline_limit: int = 100,
) -> InstrumentSnapshot | None:
    """Build one snapshot from a ticker + its recent klines + orderbook depth."""
    try:
        klines = await exchange.get_kline(
            ticker.symbol, ticker.category, interval=interval, limit=kline_limit
        )
        ob = await exchange.get_orderbook(ticker.symbol, ticker.category, depth=50)
    except Exception:
        return None
    if len(klines) < 50:
        return None

    from core.analysis.regime import classify_regime

    regime = classify_regime(klines)
    return InstrumentSnapshot(
        symbol=ticker.symbol,
        category=ticker.category,
        last_price=ticker.last_price,
        turnover_24h_usd=ticker.turnover_24h,
        spread_bps=ticker.spread_bps,
        depth_usd_1pct=ob.depth_notional_within(0.01),
        move_1h_pct=ind.pct_move(klines, 1),
        move_24h_pct=ticker.price_24h_pct,
        volume_spike_ratio=ind.volume_spike_ratio(klines),
        realized_vol_pct=regime.realized_vol_pct,
        trend_score=ind.trend_score(klines),
        zscore=ind.zscore(klines),
        annualized_funding_pct=ticker.funding_rate * (24 / 8) * 365 * 100.0,
        regime=regime.trend,
        preferred_family=regime.preferred_family,
    )


async def build_universe_snapshots(
    exchange: ExchangeClient,
    category: Category = "linear",
    *,
    max_symbols: int | None = None,
    concurrency: int = 16,
) -> list[InstrumentSnapshot]:
    """Fan out across the whole category, building a snapshot per liquid ticker."""
    tickers = await exchange.get_tickers(category)
    tickers = [t for t in tickers if t.turnover_24h > 0]
    tickers.sort(key=lambda t: t.turnover_24h, reverse=True)
    if max_symbols:
        tickers = tickers[:max_symbols]

    sem = asyncio.Semaphore(concurrency)

    async def _one(t: Ticker) -> InstrumentSnapshot | None:
        async with sem:
            return await build_snapshot(exchange, t)

    results = await asyncio.gather(*(_one(t) for t in tickers))
    return [s for s in results if s is not None]
