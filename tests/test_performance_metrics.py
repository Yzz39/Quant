import math

import numpy as np
import pandas as pd

from scripts.performance_metrics import (
    annualized_volatility,
    cagr,
    drawdown_curve,
    equity_curve_from_returns,
    format_performance_summary,
    max_drawdown,
    performance_summary,
    sharpe_ratio,
    total_return,
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


def test_equity_curve_from_returns_compounds_returns_and_preserves_index():
    returns = pd.Series(
        [0.10, None, -0.05],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
    )

    result = equity_curve_from_returns(returns, initial_equity=100.0)

    expected = pd.Series([110.0, 110.0, 104.5], index=returns.index, name="equity")
    pd.testing.assert_series_equal(result, expected)


def test_equity_curve_from_returns_rejects_non_positive_initial_equity():
    try:
        equity_curve_from_returns(pd.Series([0.01]), initial_equity=0.0)
    except ValueError as exc:
        assert "initial_equity" in str(exc)
    else:
        raise AssertionError("equity_curve_from_returns should reject non-positive initial equity")


def test_total_return_uses_first_and_last_valid_equity_values():
    equity = pd.Series([1.0, 1.1, 1.21])

    result = total_return(equity)

    assert math.isclose(result, 0.21, rel_tol=0, abs_tol=1e-12)


def test_cagr_annualizes_equity_growth_by_observed_period_count():
    equity = pd.Series([1.0, 1.1, 1.21, 1.331])

    result = cagr(equity, periods_per_year=4)

    assert math.isclose(result, 0.331, rel_tol=0, abs_tol=1e-12)


def test_cagr_returns_nan_for_single_observation():
    result = cagr(pd.Series([1.0]), periods_per_year=252)

    assert np.isnan(result)


def test_performance_summary_returns_standard_backtest_metrics():
    returns = pd.Series([0.10, -0.05, 0.02])
    equity = pd.Series([1.10, 1.045, 1.0659])

    result = performance_summary(returns, equity=equity, periods_per_year=3)

    assert set(result) == {"total_return", "cagr", "annual_vol", "max_drawdown", "sharpe_ratio"}
    assert math.isclose(result["total_return"], equity.iloc[-1] / equity.iloc[0] - 1, abs_tol=1e-12)
    assert math.isclose(result["cagr"], equity.iloc[-1] ** (3 / len(equity)) - 1, abs_tol=1e-12)
    assert math.isclose(result["annual_vol"], returns.std(ddof=1) * math.sqrt(3), abs_tol=1e-12)
    assert math.isclose(result["max_drawdown"], -0.05, abs_tol=1e-12)
    assert math.isclose(
        result["sharpe_ratio"],
        returns.mean() / returns.std(ddof=1) * math.sqrt(3),
        abs_tol=1e-12,
    )


def test_performance_summary_builds_equity_when_not_supplied():
    returns = pd.Series([0.10, -0.05, 0.02])
    generated_equity = equity_curve_from_returns(returns)

    result = performance_summary(returns, periods_per_year=3)

    assert math.isclose(result["total_return"], total_return(generated_equity), abs_tol=1e-12)
    assert math.isclose(result["max_drawdown"], max_drawdown(generated_equity), abs_tol=1e-12)


def test_format_performance_summary_formats_percentage_and_ratio_columns():
    summary = pd.DataFrame(
        {
            "total_return": [0.1234],
            "cagr": [0.0567],
            "annual_vol": [0.2],
            "max_drawdown": [-0.08],
            "sharpe_ratio": [1.234],
        },
        index=["strategy"],
    )

    result = format_performance_summary(summary)

    expected = pd.DataFrame(
        {
            "total_return": ["12.34%"],
            "cagr": ["5.67%"],
            "annual_vol": ["20.00%"],
            "max_drawdown": ["-8.00%"],
            "sharpe_ratio": ["1.23"],
        },
        index=["strategy"],
    )
    pd.testing.assert_frame_equal(result, expected)
