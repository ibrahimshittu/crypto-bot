---
id: sessions
name: Trading Sessions & Intraday Liquidity
implemented_by: core/sessions.py (SessionClock)
---

# Trading Sessions & Intraday Liquidity

Crypto trades 24/7, but volume and volatility cluster by global session. These are
**tendencies, not hard boundaries** — and weaker in crypto than forex because the market
is retail-heavy and globally distributed.

## Windows (UTC)
| Session | Window (UTC) | Character |
|---------|--------------|-----------|
| Asia (Tokyo) | 00:00–09:00 | Lower volume; more ranging. |
| London | 08:00–17:00 | Volatility builds; institutional flow. |
| New York | 13:00–22:00 | High participation. |
| **London/NY overlap** | **13:00–17:00** | **Peak volatility & volume.** |
| Low-liquidity | 02:00–06:00, 21:00–23:00 | Thin books, wider spreads. |

## Evidence vs folklore
- `[EVIDENCE]` Peak volatility at the **16:00–17:00 UTC** London/NY overlap is confirmed
  by large-sample academic analysis across many pairs/exchanges. BTC & ETH show highest
  volume in the London/NY window despite the 24/7 tape.
- `[PARTIAL]` ICT "killzones" — volume/volatility spikes are real, but the causal story
  (institutional flows) is assumed, not proven. Use the *timing*, discount the *lore*.

## How the system uses sessions
- **Bias intraday setups** to high-`liquidity_score` windows (overlap), where slippage
  is lowest and breakouts have follow-through.
- **Widen mean-reversion bands** and **shrink size** in low-liquidity hours (thin books
  → more false signals and worse fills).
- Session label + liquidity score are attached to every trade for the journal, so the
  reflection loop can learn session-conditioned rules (e.g. "skip low-cap breakouts in
  Asia low-liquidity").
