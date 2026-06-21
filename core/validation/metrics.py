"""Risk-adjusted metrics, including the Deflated Sharpe Ratio (the kill switch)."""

from __future__ import annotations

import numpy as np
from scipy import stats

# Bars-per-year for annualization, by bar interval (minutes). Crypto trades 24/7.
_BARS_PER_YEAR = {
    1: 525_600,
    5: 105_120,
    15: 35_040,
    60: 8_760,
    240: 2_190,
    1440: 365,  # daily
}


def bars_per_year(interval_minutes: int) -> float:
    return _BARS_PER_YEAR.get(interval_minutes, 8_760)


def sharpe_ratio(returns: np.ndarray, *, periods_per_year: float = 8_760) -> float:
    """Annualized Sharpe of a per-bar return series (risk-free ≈ 0)."""
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    if returns.size < 2:
        return 0.0
    sd = returns.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(returns.mean() / sd * np.sqrt(periods_per_year))


def probabilistic_sharpe_ratio(
    observed_sr: float,
    *,
    n: int,
    skew: float,
    kurtosis: float,
    benchmark_sr: float = 0.0,
) -> float:
    """P(true SR > benchmark_sr) given sample length n and return moments.

    SR here is in per-observation (non-annualized) units. kurtosis is the full
    (non-excess) kurtosis; normal == 3.
    """
    if n < 2:
        return 0.0
    denom = np.sqrt(1.0 - skew * observed_sr + (kurtosis - 1.0) / 4.0 * observed_sr**2)
    if denom <= 0 or not np.isfinite(denom):
        return 0.0
    z = (observed_sr - benchmark_sr) * np.sqrt(n - 1) / denom
    return float(stats.norm.cdf(z))


def deflated_sharpe_ratio(
    returns: np.ndarray,
    *,
    n_trials: int,
    trial_sr_variance: float | None = None,
) -> float:
    """Probability the strategy's true Sharpe > 0, deflated by the number of trials."""
    returns = np.asarray(returns, dtype=float)
    returns = returns[np.isfinite(returns)]
    n = returns.size
    if n < 8:
        return 0.0

    sr = sharpe_ratio(returns, periods_per_year=1.0)  # per-observation SR
    skew = float(stats.skew(returns))
    kurt = float(stats.kurtosis(returns, fisher=False))  # non-excess

    # Expected maximum Sharpe under the null across N independent trials.
    # E[max] ≈ sqrt(Var_trials) * ((1-γ)·Z⁻¹(1-1/N) + γ·Z⁻¹(1-1/(N·e)))
    if trial_sr_variance is None:
        # Conservative default: assume trial Sharpes vary on the order of 1 (per-year),
        # converted to per-observation. If callers know better, pass it in.
        trial_sr_variance = (1.0 / np.sqrt(max(n, 1))) ** 2

    euler_mascheroni = 0.5772156649
    nN = max(int(n_trials), 1)
    if nN <= 1:
        sr0 = 0.0
    else:
        z1 = stats.norm.ppf(1.0 - 1.0 / nN)
        z2 = stats.norm.ppf(1.0 - 1.0 / (nN * np.e))
        sr0 = np.sqrt(trial_sr_variance) * (
            (1.0 - euler_mascheroni) * z1 + euler_mascheroni * z2
        )

    return probabilistic_sharpe_ratio(
        sr, n=n, skew=skew, kurtosis=kurt, benchmark_sr=float(sr0)
    )


def max_drawdown(returns: np.ndarray) -> float:
    """Maximum drawdown of the cumulative return curve (negative fraction)."""
    returns = np.asarray(returns, dtype=float)
    if returns.size == 0:
        return 0.0
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(equity)
    drawdown = equity / peak - 1.0
    return float(drawdown.min())
