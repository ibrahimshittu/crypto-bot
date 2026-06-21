---
id: execution
name: Execution Algorithms & Market Impact
implemented_by: core/execution/
---

# Execution Algorithms & Market Impact

Good signals die from bad fills. On thin alts especially, execution choice matters as
much as the signal.

## Algorithms
| Algo | Logic | Use when |
|------|-------|----------|
| **TWAP** | Equal slices across a time window | Calm markets; simple schedule. |
| **VWAP** | Trade in proportion to volume profile | Benchmark to daily VWAP; hide signaling. |
| **POV** | Hold a fixed % of live volume | Adapt to real-time liquidity; uncertain end time. |
| **Implementation Shortfall** | Minimize cost vs arrival price; front-loaded | Alpha decays fast; delay risk dominates. |
| **Iceberg** | Show only a small tip, refill | Reduce signaling on large orders. |

Bybit exposes TWAP / iceberg / chase / POV via `/v5/strategy/*` (and the Bybit `skills`
`strategy` module) — prefer these for any order large vs book depth.

## Square-root law of market impact `[EVIDENCE — robust empirical regularity]`
`I(Q) ≈ Y · σ · √(Q / V)`  where `Q` = order size, `V` = daily volume, `σ` = daily vol,
`Y` ≈ O(1).

Implications baked into our cost model:
- Impact grows with **√(participation)**, not linearly — **linear cost models badly
  underestimate** large-order cost.
- Impact depends mainly on **total size Q**, roughly independent of how long you stretch
  it (at moderate participation). So *size* matters more than *schedule*.

## System policy
- Small orders relative to depth → marketable limit / IOC.
- Order > ~X% of top-of-book depth → route via TWAP/POV/iceberg and/or split across time
  (bias toward high-`liquidity_score` sessions).
- The pre-trade check estimates impact via the square-root law and **rejects** fills
  whose modeled cost erases the signal's expected edge.
