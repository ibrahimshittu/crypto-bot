---
id: funding_carry_basis
family: market_neutral_carry
name: Funding-Rate Harvesting / Cash-and-Carry Basis
products: [spot, linear]
holding_period: days_to_months
timeframes: [60, D]
capital_floor_usd: 1000
infra: low
sizing: delta_neutral_two_leg
default_params:
  min_annualized_funding_pct: 10    # enter when annualized carry exceeds this
  exit_annualized_funding_pct: 3    # exit when carry decays below this
  funding_interval_hours: 8
  max_leverage_perp_leg: 2.0
  rebalance_delta_tolerance: 0.05   # re-hedge if net delta drifts past ±5%
edge_after_fees: positive_lower_variance
evidence: strong                    # EVIDENCE: segmentation-driven persistence
---

# Funding-Rate Harvesting / Cash-and-Carry Basis

## Thesis
Perpetual futures trade above spot in bullish regimes; longs pay shorts **funding**
every `funding_interval_hours`. Going **long spot + short perp** in equal notional is
**delta-neutral** and collects funding. Persistence is driven by market segmentation —
regulated institutions often can't hold spot, sustaining the premium. `[EVIDENCE]`
(BIS WP 1087; CEPR crypto carry; CMU carry-trade study.)

## Mechanics
- **Perp-funding variant:** long spot `X`, short `X` notional of the perp. Shorts
  receive funding while basis is positive. Net price exposure ≈ 0.
- **Dated-future variant (contango):** lock the calendar premium, hold to expiry
  convergence.

## Entry / Exit
- **Entry:** when annualized funding/basis > `min_annualized_funding_pct`.
- **Exit:** when carry decays below `exit_annualized_funding_pct`, **or funding flips
  negative** (now you'd be paying), or the spot-perp spread closes.
- **Rebalance:** re-hedge if net delta drifts past `rebalance_delta_tolerance`.

## Capital note (important for small accounts)
The two-leg structure ties up ~2× notional (spot + perp margin), so **return on total
capital ≈ half the headline funding rate**. Example: 0.01%/8h ≈ 0.03%/day ≈ ~11% APR on
notional ≈ ~5.5% on total capital. Account for both legs' fees on entry and exit.

## Holding period
Days to months, until carry decays.

## Risks
- **Short-leg liquidation** in a sharp rally before margin top-up: spot gain is
  unrealized while the perp loss crystallizes. Keep `max_leverage_perp_leg` low and
  maintain margin buffer. This is the primary blow-up mode.
- Funding flips negative; spot↔perp cross-margin not available on all venues; execution
  gap between the two legs; exchange/counterparty risk.
- `[FOLKLORE]` 2021-era carry Sharpes (CMU reports ~7–12 over Aug'20–Jun'22) captured a
  boom and **will not recur** at that level — treat as regime-dependent.

## Realistic edge after fees
Real, lower-variance, delta-neutral. The most evidence-based carry trade available to a
small account — but returns scale down with the funding rate and are not guaranteed.

## References
BIS WP 1087; CEPR "Crypto Carry"; CMU CarryTrade; Hyperdash basis-trading guide.
