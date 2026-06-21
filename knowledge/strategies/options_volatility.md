---
id: options_volatility
family: volatility
name: Options / Volatility (Vol-Risk-Premium)
products: [option]
holding_period: days_to_weeks
infra: medium_to_high
status: phase_later
edge_after_fees: positive_with_tail_risk
evidence: leaning_strong     # VRP is a documented premium; tail risk is real
---

# Options / Volatility

> **Status: later phase.** Bybit supports options; this requires a greeks/vol-surface
> stack. Documented now so the system understands vol regimes and dealer gamma.

## Core trade — sell the volatility risk premium (VRP)
BTC/ETH **implied vol tends to exceed subsequent realized vol**, so systematic
short-vol (covered calls, cash-secured puts, delta-hedged short strangles/straddles) has
a base-case edge. `[EVIDENCE-leaning]`

## Signal infrastructure
- **DVOL** (Deribit 30-day annualized IV index). Rule of thumb: expected daily move ≈
  DVOL/20 (DVOL 90 → ~4.5%/day).
- **Skew:** 25-delta put IV vs call IV; puts often richer in risk-off.
- **Dealer gamma:** long-gamma dealers dampen moves (buy dips/sell rips); short-gamma
  **amplifies** — an exploitable order-flow signal around large open-interest strikes.

## Risks
Short-vol is "picking up pennies in front of a steamroller" — **tail blow-ups, gap risk,
pin/gamma risk**, and thin liquidity in far strikes. Position sizing and hard tail
hedges are non-negotiable. Continuous delta-hedging required.

## References
Deribit DVOL docs; crypto VRP literature; FalconX options-market notes.
