import math

import numpy as np
import pandas as pd

from scripts.performance_metrics import (
    annualized_volatility,
    drawdown_curve,
    max_drawdown,
    sharpe_ratio,
)


def test_annualized_volatility_scales_sample_return_std_by_square_root_of_periods():
    returns = pd.Series([0.01, -0.02, 0.03, 0.00])

    result = annualized_volatility(returns, periods_per_year=252)

    expected = returns.std(ddof=1) * math.sqrt(252)
    assert math.isclose(result, expected, rel_tol=0, abs_tol=1e-12)


def test_annualized_volatility_ignores_missing_returns():
    returns = pd.Series([0.01, None, -0.02, 0.03, None, 0.00])

    result = annualized_volatility(returns, periods_per_year=252)

    expected = pd.Series([0.01, -0.02, 0.03, 0.00]).std(ddof=1) * math.sqrt(252)
    assert math.isclose(result, expected, rel_tol=0, abs_tol=1e-12)


def test_sharpe_ratio_annualizes_excess_return_over_risk_free_rate():
    returns = pd.Series([0.01, -0.02, 0.03, 0.00])
    annual_risk_free_rate = 0.03
    periods_per_year = 252

    result = sharpe_ratio(
        returns,
        periods_per_year=periods_per_year,
        annual_risk_free_rate=annual_risk_free_rate,
    )

    period_rf = (1 + annual_risk_free_rate) ** (1 / periods_per_year) - 1
    excess_returns = returns - period_rf
    expected = excess_returns.mean() / excess_returns.std(ddof=1) * math.sqrt(periods_per_year)
    assert math.isclose(result, expected, rel_tol=0, abs_tol=1e-12)


def test_sharpe_ratio_returns_nan_when_volatility_is_zero():
    result = sharpe_ratio(pd.Series([0.01, 0.01, 0.01]), periods_per_year=252)

    assert np.isnan(result)


def test_drawdown_curve_uses_running_peak_and_preserves_index():
    equity = pd.Series(
        [100.0, 120.0, 90.0, 150.0, 135.0],
        index=pd.to_datetime([
            "2026-01-01",
            "2026-01-02",
            "2026-01-03",
            "2026-01-04",
            "2026-01-05",
        ]),
        name="strategy_equity",
    )

    result = drawdown_curve(equity)

    expected = pd.Series(
        [0.0, 0.0, -0.25, 0.0, -0.10],
        index=equity.index,
        name="drawdown",
    )
    pd.testing.assert_series_equal(result, expected)


def test_max_drawdown_returns_worst_negative_drawdown():
    equity = pd.Series([1.0, 1.2, 0.9, 1.5, 1.35])

    result = max_drawdown(equity)

    assert math.isclose(result, -0.25, rel_tol=0, abs_tol=1e-12)


def test_max_drawdown_is_zero_when_equity_never_falls_below_peak():
    equity = pd.Series([1.0, 1.0, 1.1, 1.3])

    result = max_drawdown(equity)

    assert result == 0.0


def test_drawdown_functions_ignore_missing_values_without_changing_valid_calculation():
    equity = pd.Series([1.0, None, 1.25, 1.0, None, 1.5])

    curve = drawdown_curve(equity)
    result = max_drawdown(equity)

    expected = pd.Series([0.0, float("nan"), 0.0, -0.2, float("nan"), 0.0], name="drawdown")
    pd.testing.assert_series_equal(curve, expected)
    assert math.isclose(result, -0.2, rel_tol=0, abs_tol=1e-12)


def test_drawdown_functions_reject_non_positive_equity_values():
    bad_equity = pd.Series([1.0, 0.0, 1.1])

    try:
        drawdown_curve(bad_equity)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("drawdown_curve should reject non-positive equity values")

    try:
        max_drawdown(bad_equity)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("max_drawdown should reject non-positive equity values")
