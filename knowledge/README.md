# Domain Knowledge Base (the "skills")

This directory is the system's encoded trading knowledge — the strategies, market
structure, session behavior, risk doctrine, execution algorithms, and validation
discipline that professional crypto desks use. Every agent reads from here; the
deterministic core implements what these documents specify.

## How it's used

- **Agents** load relevant modules into context (the orchestrator selects by
  regime/session; the strategy agent loads the matching strategy file).
- **The `core.knowledge` loader** parses the YAML frontmatter of each module so
  strategy parameters, holding periods, and risk caps are available as data, not just
  prose. Keep frontmatter accurate — it is machine-read.
- **Provenance discipline:** every non-trivial claim is tagged `[EVIDENCE]`
  (academically/empirically supported) or `[FOLKLORE]` (trader-blog claim, treat as a
  hypothesis to be validated). Performance numbers from blogs are illustrative, not
  investable, until re-validated by our own backtest gate.

## Modules

| Folder | Contents |
|--------|----------|
| `strategies/` | One file per strategy family: signal, entry/exit, holding period, capital/infra, risks, realistic edge after fees, math. |
| `sessions/` | Asia/London/NY windows, the London-NY overlap, low-liquidity hours, session-conditioned behavior. |
| `microstructure/` | Order book, slippage, funding rates, basis, liquidations/ADL. |
| `risk/` | Position sizing, drawdown limits, leverage, correlation, tail risk. |
| `execution/` | TWAP/VWAP/POV/IS/iceberg, square-root market-impact law. |
| `validation/` | López de Prado: triple-barrier, meta-labeling, frac-diff, purged/combinatorial CV, deflated Sharpe. The gatekeeper doctrine. |
| `data_sources/` | Catalog of news/sentiment/on-chain feeds with cost & reliability. |

## The one rule that overrides everything

A strategy may only be allocated real capital **after** it passes the validation gate
in `validation/` with transaction costs and slippage modeled. In-sample Sharpe is not
evidence. This is the single most important guardrail in the system.
