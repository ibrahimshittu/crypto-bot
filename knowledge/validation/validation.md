---
id: validation
name: Backtest Validation Doctrine (López de Prado)
implemented_by: core/validation/
gatekeeper: true
---

# Backtest Validation Doctrine — the Gatekeeper

**No strategy is allocated real capital until it passes this gate with transaction costs
and slippage modeled.** ~90% of crypto strategy backtests are overfit and die live.
In-sample Sharpe is *not* evidence. From López de Prado, *Advances in Financial Machine
Learning*.

## Techniques (all implemented in `core/validation/`)

### 1. Triple-barrier labeling
Label each observation by which barrier hits first within a holding window:
upper (profit-take), lower (stop-loss), vertical (max holding time). Barriers set as
multiples of **rolling volatility** → path-dependent, economically meaningful labels
(not naïve fixed-horizon returns).

### 2. Meta-labeling
A secondary model decides **whether to act** on the primary signal and **how much** to
size — improving precision/F1 and bolting ML sizing onto a rule without changing its
direction call.

### 3. Fractional differentiation
A "dimmer switch" between raw prices (full memory, non-stationary) and returns
(stationary, memory destroyed). Use the **minimum** differencing order `d` that passes an
ADF stationarity test while **retaining maximum memory** — better features.

### 4. Sample weights / uniqueness
Overlapping labels violate IID. Weight samples by label **uniqueness** and return
attribution so concurrent/overlapping outcomes don't double-count.

### 5. Combinatorial Purged Cross-Validation (CPCV)
Generate many train/test path combinations; **purge** training samples whose label
windows overlap the test set; add an **embargo** after each test block. Kills leakage
from serial correlation and yields a **distribution** of backtest paths, not one number.

### 6. Deflated Sharpe Ratio (DSR) — the kill switch
The best in-sample Sharpe across `N` trials is upward-biased by selection. DSR corrects
the observed Sharpe for: number of trials `N`, variance of trial Sharpes, and
non-normality (skew/kurtosis), giving the probability the **true** Sharpe > 0.

## The gate (pass criteria)
A strategy/parameterization is **tradeable** only if, on the CPCV path distribution and
**net of the cost model**:
1. Median out-of-sample Sharpe > a configured floor, AND
2. **Deflated Sharpe Ratio** indicates statistically significant edge (e.g. DSR p < 0.05
   given the trial count), AND
3. No single CPCV path shows catastrophic drawdown beyond the risk policy.

Anything failing this is logged and benched — including pretty in-sample equity curves.
Edge decay is assumed: re-validate periodically; demote degrading strategies.
