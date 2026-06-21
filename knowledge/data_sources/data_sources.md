---
id: data_sources
name: Market, News, Sentiment & On-Chain Data Sources
---

# Data Sources

## Market data (primary)
- **Bybit V5 REST** — klines, orderbook, tickers, funding history, open interest,
  instruments-info. **WebSocket** — public (orderbook/trades/kline/tickers) + private
  (order/position/wallet/execution). Persist OHLCV/funding to TimescaleDB.

## News
| Source | Cost | Notes |
|--------|------|-------|
| **CryptoPanic** | Free tier | Aggregated headlines + sentiment index; 5–30 min delay. Start here. |
| NewsAPI | Free/paid | Broader news; needs crypto filtering. Optional. |

## Social sentiment (confirmation only — high noise)
| Source | Cost | Notes |
|--------|------|-------|
| **LunarCrush** | Free → $99+/mo | Social volume/sentiment, influencer ranking. |
| **Santiment** | $49+/mo | Social + on-chain + dev metrics; real-time on higher tiers. |
| X / Reddit | Free APIs | Raw, noisy; needs NLP. Later phase. |

`[EVIDENCE]` Crowd signals have **mixed** predictive power and best used **combined with
on-chain** (whale moves, exchange flows) — ~30–40% signal improvement when fused, not as
a standalone alpha. The sentiment agent therefore treats social as a *confirmation*
input and separates **fact** from **subjectivity** (FS-ReasoningAgent finding).

## On-chain (later phase)
| Source | Cost | Notes |
|--------|------|-------|
| Glassnode | $49+/mo | 300–1500+ metrics; exchange flows, SOPR, active addresses. |
| Nansen | Paid | Wallet-level whale tracking. |
| Dune | Free → paid | Custom on-chain SQL. |

Most actionable on-chain signals `[EVIDENCE]`: large exchange **inflows** (sell pressure),
dormant-coin movement, whale thresholds (BTC ≥1,000; ETH ≥10,000), active-address growth
(3–6 month trend, not intraday).

## Reliability policy
Assume 99.9% feed uptime, not 100%: retry with backoff, dedupe news, timestamp-align
news vs price to avoid look-ahead, and degrade gracefully (a missing sentiment feed
must not block a validated mechanical signal).
