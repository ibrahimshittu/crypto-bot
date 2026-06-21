---
id: mean_reversion_statarb
family: market_neutral
name: Mean-Reversion / Statistical-Arbitrage Pairs
products: [spot, linear]
holding_period: hours_to_days
timeframes: [60, 240]
capital_floor_usd: 500
infra: low_to_medium
sizing: z_score_scaled
default_params:
  coint_pvalue_max: 0.05
  ou_halflife_max_bars: 48      # discard pairs slower than the trading horizon
  lookback_bars: 720            # window for beta + spread stats
  z_enter: 2.0
  z_add: 2.5
  z_exit: 0.3
  z_stop: 3.5                   # cointegration-break stop
  max_pairs: 10
edge_after_fees: thin_positive
evidence: mixed                 # method EVIDENCE; single-pair blog Sharpe FOLKLORE
---

# Mean-Reversion / Statistical-Arbitrage Pairs

## Thesis
Two cointegrated assets share a stationary spread; deviations revert. Trading the
spread is **market-neutral**, so it earns in chop and sideways regimes where momentum
bleeds. `[EVIDENCE: method]`

## Build pipeline (deterministic)
1. **Candidate pairs** from the scanned universe (same sector / high correlation).
2. **Cointegration test** — Engle-Granger (or Johansen for baskets). Keep pairs with
   p < `coint_pvalue_max`. Re-test on a rolling basis; cointegration decays.
3. **Spread** `S = priceA − β·priceB` (β from rolling OLS / Kalman).
4. **Ornstein-Uhlenbeck fit** on the residual → mean-reversion speed and **half-life**.
   Discard pairs with half-life > `ou_halflife_max_bars` (too slow to trade).
5. **Trade the z-score** of the spread.

## Entry / Exit
- **Entry:** open the spread when `|z| > z_enter` (short the rich leg, long the cheap
  leg, β-weighted). Optionally scale to `z_add`.
- **Exit:** `|z| ≤ z_exit` (reversion to mean).
- **Stop:** `|z| > z_stop` → assume cointegration broke; exit and quarantine the pair.
- The z-score at entry approximates the trade's ex-ante Sharpe — size proportionally,
  inside the risk engine caps.

## Holding period
Hours to a few days, set by the estimated half-life.

## Risks
- **Cointegration breakdown / structural regime change** — the dangerous tail: the
  spread keeps widening instead of reverting. The `z_stop` is mandatory.
- Crowding compresses the edge; **transaction costs** erode small spreads — only trade
  spreads wide enough to clear modeled costs.
- Look-ahead bias in β estimation (use only past data for the rolling fit).
- `[FOLKLORE]` A cited BTC-ETH pair "Sharpe ~2.45" is single-pair, in-sample. Re-validate.

## Realistic edge after fees
Thin. Viable only with disciplined cost modeling and enough pairs to diversify the
idiosyncratic break risk. Plausible post-cost Sharpe ≈ 0.8–1.3 across a basket.

## References
Engle-Granger / Johansen cointegration; Ornstein-Uhlenbeck pairs (arXiv 2412.12458);
CoinAPI stat-arb notes.
