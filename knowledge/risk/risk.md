---
id: risk
name: Risk Management Doctrine
implemented_by: core/risk/
non_negotiable: true
---

# Risk Management Doctrine

Risk control beats alpha. These rules are enforced deterministically by `core/risk/` and
can veto any order regardless of agent conviction.

## Position sizing (capital-aware)
- Every order is sized as a **fraction of current equity** (read live from Bybit), never
  a fixed dollar amount.
- **Fixed-fractional (default):** risk `risk_per_trade_pct` (1–2%) of equity per trade,
  converted to quantity from entry price and stop distance:
  `qty = (equity × risk_pct) / (entry − stop)`.
- **Fractional Kelly (optional):** use **10–25% of full Kelly**; full Kelly is far too
  volatile for crypto (50%+ drawdowns). `f* = (p·b − q) / b`.
- **Minimum-order guard:** if the risk-sized qty is below Bybit's per-symbol minimum,
  skip or flag — never round *up* into oversizing a tiny account.
- **Slippage gate:** reject if intended size > configured % of order-book depth.

## Loss limits & circuit breakers
- Max loss per trade: **1–2%** of equity.
- **Daily circuit breaker:** halt new entries if daily P&L ≤ `−daily_loss_halt_pct`
  (default −5%).
- **Drawdown ladder:** −5% → cut all positions 25%; −10% → cut 50%.
- Recovery math (why caps matter): −10% needs +11.1%, −20% needs +25%, **−50% needs
  +100%**. Losses compound against you.

## Leverage (perps)
- Hard cap `max_leverage` (default 3×, ceiling 5×). Maintain margin buffer; enforce a
  liquidation-distance guard; exits are `reduceOnly`.

## Portfolio level
- **Correlation guard:** positions with >0.7 rolling correlation share one risk budget
  (don't take 5 correlated longs as if independent).
- Prefer uncorrelated sleeves (trend vs mean-reversion vs carry; spot vs perp).
- **Tail risk:** crypto has fat tails — use **Expected Shortfall (CVaR)**, not just VaR.
  BTC vol (~54% annualized) ≫ gold/equities; size accordingly.

## Operational safety
Kill switch + manual override; exchange-health/latency monitor; exponential-backoff
retries; pre-fund both legs of delta-neutral trades.
