---
id: microstructure
name: Crypto Market Microstructure
---

# Crypto Market Microstructure

## Order book & slippage
- Depth concentrates within ±1–2% of mid; market-order slippage rises **non-linearly**
  with size relative to available depth.
- **Default modeling assumption: 0.3–0.5% slippage per side** on liquid pairs; **2–5%**
  on thin alts for ~1% notional. `[EVIDENCE]` The universe scanner must gate size vs
  book depth so we never assume liquidity that isn't there.

## Funding rates (perps)
- Perps stay tethered to spot via **funding** every 8h: if perp > spot, longs pay
  shorts (positive funding), and vice versa.
- Typical 0.01–0.10% per 8h (≈3–36% annualized); **positive 70–80% of the time** in bull
  markets. Drives the carry trade (see `strategies/funding_carry_basis.md`). `[EVIDENCE]`

## Basis
- Spread between perp/future and spot. Positive basis (contango) = bullish positioning;
  converges at expiry for dated futures. Tradeable via cash-and-carry.

## Liquidations & ADL
- Leveraged positions are force-closed at maintenance margin. Clustered liquidations →
  **cascades**: forced flow pushes price to the next cluster, chaining. `[EVIDENCE]`
- **Auto-Deleveraging (ADL)**: when the insurance fund can't cover, the exchange closes
  opposing positions — a tail risk for the carry short leg.
- Implication: keep leverage low, watch OI/funding extremes, and treat thin books +
  high leverage as a cascade-risk regime.

## What the system does with this
- Slippage + fee model is applied in **every** backtest and pre-trade check.
- Funding/basis feed the carry strategy and a "crowded positioning" risk flag.
- Liquidation/OI context informs the order-flow overlay and execution timing.
