"""Triple-barrier labeling (López de Prado)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_volatility(close: pd.Series, span: int = 50) -> pd.Series:
    """EWM volatility of log returns, used to scale the barriers."""
    log_ret = np.log(close / close.shift(1))
    return log_ret.ewm(span=span).std()


def triple_barrier_labels(
    close: pd.Series,
    *,
    pt_mult: float = 2.0,
    sl_mult: float = 2.0,
    max_hold: int = 24,
    vol_span: int = 50,
) -> pd.DataFrame:
    """Return a DataFrame indexed like `close` with columns:
       label (+1/-1/0), ret (realized return to the touched barrier), hold (bars held).

    pt_mult / sl_mult scale the rolling volatility into the profit-take / stop-loss
    barriers; max_hold is the vertical barrier in bars.
    """
    close = close.astype(float)
    vol = rolling_volatility(close, span=vol_span)
    n = len(close)
    values = close.to_numpy()

    labels = np.zeros(n, dtype=int)
    rets = np.full(n, np.nan)
    holds = np.zeros(n, dtype=int)

    for i in range(n):
        v = vol.iloc[i]
        if not np.isfinite(v) or v == 0:
            continue
        entry = values[i]
        upper = entry * (1.0 + pt_mult * v)
        lower = entry * (1.0 - sl_mult * v)
        end = min(i + max_hold, n - 1)

        label, ret, hold = 0, values[end] / entry - 1.0, end - i
        for j in range(i + 1, end + 1):
            price = values[j]
            if price >= upper:
                label, ret, hold = 1, price / entry - 1.0, j - i
                break
            if price <= lower:
                label, ret, hold = -1, price / entry - 1.0, j - i
                break
        labels[i] = label
        rets[i] = ret
        holds[i] = hold

    return pd.DataFrame({"label": labels, "ret": rets, "hold": holds}, index=close.index)
