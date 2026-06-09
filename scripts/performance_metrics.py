"""Performance metric helpers for ETF/backtest study scripts."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd


def _to_equity_series(equity: pd.Series | Iterable[float]) -> pd.Series:
    """Convert an equity curve to numeric pandas Series and validate it."""
    if isinstance(equity, pd.Series):
        series = equity.copy()
    else:
        series = pd.Series(list(equity))

    series = pd.to_numeric(series, errors="coerce")
    valid = series.dropna()

    if valid.empty:
        raise ValueError("equity must contain at least one non-missing value")
    if (valid <= 0).any():
        raise ValueError("equity values must be positive")

    return series


def drawdown_curve(equity: pd.Series | Iterable[float]) -> pd.Series:
    """Return the drawdown curve of an equity/net-value series.

    Drawdown is calculated at each point as::

        current_equity / historical_running_peak - 1

    New highs are therefore ``0``; values below the previous high are negative.
    Missing values are preserved as missing values and ignored by the running
    peak calculation, matching pandas ``cummax`` behavior.
    """
    series = _to_equity_series(equity)
    running_peak = series.cummax()
    result = series / running_peak - 1.0
    result.name = "drawdown"
    return result


def max_drawdown(equity: pd.Series | Iterable[float]) -> float:
    """Return the maximum drawdown as the worst negative value in the curve."""
    return float(drawdown_curve(equity).min())
