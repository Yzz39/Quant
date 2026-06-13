"""Performance metric helpers for ETF/backtest study scripts."""

from __future__ import annotations

from collections.abc import Iterable
import math

import numpy as np
import pandas as pd


def _to_returns_series(returns: pd.Series | Iterable[float]) -> pd.Series:
    """Convert a return series to numeric pandas Series and drop missing values."""
    if isinstance(returns, pd.Series):
        series = returns.copy()
    else:
        series = pd.Series(list(returns))

    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        raise ValueError("returns must contain at least one non-missing value")

    return series


def annualized_volatility(
    returns: pd.Series | Iterable[float],
    periods_per_year: int = 252,
) -> float:
    """Return annualized volatility from periodic returns.

    The function uses sample standard deviation (``ddof=1``), which is the
    common choice when estimating volatility from historical return samples.
    For daily returns, ``periods_per_year`` is usually 252.
    """
    series = _to_returns_series(returns)
    if len(series) < 2:
        return np.nan
    return float(series.std(ddof=1) * math.sqrt(periods_per_year))


def sharpe_ratio(
    returns: pd.Series | Iterable[float],
    periods_per_year: int = 252,
    annual_risk_free_rate: float = 0.0,
) -> float:
    """Return annualized Sharpe ratio from periodic returns.

    Sharpe ratio measures excess return per unit of volatility::

        Sharpe = mean(period_return - period_risk_free_rate)
                 / std(period_return - period_risk_free_rate)
                 * sqrt(periods_per_year)

    ``annual_risk_free_rate`` is converted into a per-period rate by compound
    de-annualization before subtracting it from each period return.
    """
    series = _to_returns_series(returns)
    if len(series) < 2:
        return np.nan

    period_risk_free_rate = (1.0 + annual_risk_free_rate) ** (1.0 / periods_per_year) - 1.0
    excess_returns = series - period_risk_free_rate
    volatility = excess_returns.std(ddof=1)
    if volatility == 0 or np.isnan(volatility):
        return np.nan

    return float(excess_returns.mean() / volatility * math.sqrt(periods_per_year))


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
