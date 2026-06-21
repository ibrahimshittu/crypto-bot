---
id: order_flow_liquidation
family: order_flow
name: Order-Flow / Liquidation-Cascade
products: [linear]
holding_period: seconds_to_hours
infra: medium
status: discretionary_heuristic
edge_after_fees: situational
evidence: weak           # largely FOLKLORE / discretionary, hard to backtest
---

# Order-Flow / Liquidation-Cascade

> **Status: heuristic / confirmation-only.** Little peer-reviewed validation; easy to be
> early and wrong. Use as *context* for other strategies and for execution timing, not
> as a standalone money-maker until our gate proves a specific rule.

## Signal
- Crowded leverage: open interest skewed one way + funding extreme.
- Thinning book depth near visible **liquidation clusters**.
- Order-flow / bid-ask imbalance.

## Cascade mechanics `[EVIDENCE: mechanism]`
Forced liquidations push price into the next liquidation cluster → chain reaction.
Conditions: high leverage + thin liquidity + auto-liquidation. (Oct 2025: ~$19B
liquidated in 36h is a documented example.)

## Playbooks
- **Fade the climax** (preferred, mean-reverting): buy the over-extended forced-selling
  flush, betting exhaustion → bounce. Lower-risk, fits our mean-reversion tooling.
- **Front-run** (aggressive): short into a trapped-long cluster at the support about to
  break. High risk, requires real-time liquidation + depth feeds.

## Risks
Hard to backtest; timing-sensitive; needs live liquidation/depth data; largely
discretionary. Treat outputs as a **risk/timing overlay**, not a primary alpha.

## References
Amberdata liquidation analytics; Oct 2025 cascade post-mortems.
