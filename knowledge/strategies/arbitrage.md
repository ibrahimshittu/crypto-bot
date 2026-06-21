---
id: arbitrage
family: arbitrage
name: Cross-Exchange & Triangular Arbitrage
products: [spot, linear]
holding_period: ms_to_seconds
infra: high
status: documented_excluded_at_our_size
edge_after_fees: thin_competitive
evidence: strong          # EVIDENCE: empirically measured, but tiny net edge
---

# Cross-Exchange & Triangular Arbitrage

> **Status: documented, EXCLUDED at our latency/infra.** Listed so the system knows it
> exists and why it can't compete here.

## Mechanics
- **Spatial / cross-exchange:** same asset priced differently on two venues — buy cheap,
  sell dear, near-simultaneously, with inventory pre-positioned on both sides.
- **Triangular:** a closed loop of three pairs (e.g. BTC/USDT → BTC/ETH → ETH/USDT)
  whose product of rates ≠ 1.

## Why we don't run it
- **Net edge is ~9–12 bps per trade** and only profitable when the gross gap clears
  fees + slippage on every leg. `[EVIDENCE]` (arXiv 2002.12274: triangular conversions
  profitable ~95% of the time but mean net ~9.3 bps.) Requires colocation, multi-venue
  inventory, and leg-risk management — a pro infra game. Deviations have narrowed
  sharply as the market matured.

## Risks
Leg risk (one leg fills, others move), withdrawal/transfer latency, exchange outages,
stale quotes, fierce competition.

## References
arXiv 2002.12274; Gemini arbitrage primer.
