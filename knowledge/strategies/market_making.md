---
id: market_making
family: liquidity_provision
name: Market Making (Avellaneda-Stoikov)
products: [spot, linear]
holding_period: seconds_to_minutes
timeframes: [tick, 1]
capital_floor_usd: 250000
infra: high
sizing: inventory_aware
status: documented_excluded_at_our_size
default_params:
  gamma: 0.1            # inventory risk aversion
  sigma_lookback: 60
  kappa_estimate: 1.5   # order-arrival / book-liquidity density
edge_after_fees: structural_requires_infra
evidence: strong        # A-S is the canonical academic framework
---

# Market Making (Avellaneda-Stoikov)

> **Status: documented for completeness, EXCLUDED at our capital/infra.** This is the
> core business of Jump/Wintermute/GSR/Citadel and depends on latency, rebates, and
> balance sheet we don't have. Kept here so the system *understands* the dominant flow
> it's trading against — not to run it.

## Framework
Quote two-sided around fair value; skew quotes by inventory. Avellaneda-Stoikov (2008):

- **Reservation price:** `r(s,q,t) = s − q·γ·σ²·(T−t)` — shifts quotes away from current
  inventory `q` (push it back toward target).
- **Optimal spread:** `δ_a + δ_b = γ·σ²·(T−t) + (2/γ)·ln(1 + γ/κ)`.
- Params: `s` mid, `q` inventory, `γ` risk aversion, `σ` volatility, `κ` book liquidity,
  `(T−t)` horizon. Wider σ → wider spread; larger γ → de-risk faster.

## Why we don't run it
- Edge per round-trip is tiny; profitability comes from **speed + maker rebates + huge
  trade count**. Without colocation and low fees, **adverse selection** (informed flow
  picking off stale quotes) dominates and you lose.

## Use in this system
- As **knowledge**: the order-flow and microstructure agents reason about dealer
  inventory/gamma and where MM quotes thin out — informs liquidation-cascade and
  execution decisions.

## References
Avellaneda & Stoikov (2008); Hummingbot A-S guides.
