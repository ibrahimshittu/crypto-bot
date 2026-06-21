---
id: momentum_trend
family: directional
name: Momentum / Trend-Following
products: [spot, linear]
holding_period: hours_to_days
timeframes: [60, 240, D]
capital_floor_usd: 100
infra: low
sizing: trend_strength_scaled
default_params:
  ts_mom_lookback: 90          # bars for time-series momentum sign
  fast_ma: 20
  slow_ma: 100
  donchian_entry: 20           # breakout channel (bars)
  donchian_exit: 10
  atr_period: 14
  atr_stop_mult: 2.5
  trend_filter_ema: 200        # only longs above, shorts below
edge_after_fees: positive_but_regime_dependent
evidence: mixed                # mechanism EVIDENCE; blog Sharpe numbers FOLKLORE
---

# Momentum / Trend-Following

## Thesis
Crypto exhibits strong, persistent trends and fat-tailed moves. Trend-following does
not aim to beat buy-and-hold in raw return during a bull run; its documented value is
**risk management** — cutting exposure in downtrends, reducing drawdown, and improving
risk-adjusted return. `[EVIDENCE: mechanism]`

## Signals (implement all; ensemble or pick by regime)
1. **Time-series momentum** — go long if sign of trailing `ts_mom_lookback`-bar return
   is positive, short if negative (perps only). Classic cross-asset TSMOM result.
2. **MA crossover** — long when `fast_ma > slow_ma`, flat/short otherwise.
3. **Donchian breakout (Turtle-style)** — enter long on a new `donchian_entry`-bar
   high while price > `trend_filter_ema`; exit on `donchian_exit`-bar low or ATR stop.
4. **Trend filter** — only take longs above the `trend_filter_ema`, shorts below it.

## Entry / Exit
- **Entry:** breakout or crossover *confirmed on bar close* (never intra-bar — avoids
  look-ahead). Optionally require `liquidity_score` from SessionClock above a floor.
- **Stop:** `atr_stop_mult × ATR(atr_period)` from entry.
- **Exit:** opposing channel/crossover, ATR trailing stop, or time-stop (triple-barrier
  vertical barrier).
- **Sizing:** scale position with trend strength but always inside the risk engine's
  per-trade % cap (see `risk/`).

## Holding period
Days to a few weeks for the channel variants; shorter on intraday timeframes.

## Risks
- **Whipsaw** in ranging/choppy regimes — the dominant failure mode. Pair with a regime
  filter (only trend when realized vol / ADX indicates a trend).
- Fat-tail gap risk; regime change; **backtest overfitting** of MA lengths.
- `[FOLKLORE]` Blog backtests citing ~116% APR / Sharpe ~1.7 for 20/100 BTC crossover
  are in-sample, long-only-crypto, survivorship-prone. Do **not** trust until our gate
  re-validates with costs.

## Realistic edge after fees
Modest and regime-dependent. Best Sharpe historically with short-ish MAs (~10–30 bars).
Treat target Sharpe ≈ 0.7–1.2 *after costs* as plausible; anything above ~1.5 in
backtest is a red flag for overfitting.

## References
Grayscale "The Trend is Your Friend"; QuantInsti Donchian; cross-asset TSMOM literature.
