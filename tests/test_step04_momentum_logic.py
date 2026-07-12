import math

import pytest

from scripts.step04_momentum_logic import (
    efficiency_momentum_score,
    momentum_score,
    ols_slope_r2_score,
    absolute_momentum_target,
    rank_momentum,
    recent_confirmation_target,
    safe_buy_target_value,
    top1_gap,
    trend_outcome,
)


def test_momentum_score_uses_lookback_plus_one_prices():
    assert momentum_score([100, 101, 110], lookback=2) == pytest.approx(0.10)


def test_momentum_score_rejects_short_or_invalid_prices():
    with pytest.raises(ValueError):
        momentum_score([100, 101], lookback=2)
    with pytest.raises(ValueError):
        momentum_score([0, 101, 110], lookback=2)


def test_m3a_perfect_exponential_trend_has_r2_one():
    prices = [100.0 * 1.02**index for index in range(5)]
    result = ols_slope_r2_score(prices, lookback=4)
    assert result["beta"] == pytest.approx(math.log(1.02))
    assert result["r_squared"] == pytest.approx(1.0)
    assert result["score"] == pytest.approx(math.log(1.02))


def test_m3a_uses_lookback_plus_one_prices_and_rejects_nonpositive():
    with pytest.raises(ValueError):
        ols_slope_r2_score([100, 101, 102], lookback=3)
    with pytest.raises(ValueError):
        ols_slope_r2_score([100, 0, 102, 103], lookback=3)
    with pytest.raises(ValueError):
        ols_slope_r2_score([100, float("nan"), 102, 103], lookback=3)
    with pytest.raises(ValueError):
        ols_slope_r2_score([100, float("inf"), 102, 103], lookback=3)


def test_m3b_monotonic_path_has_efficiency_one():
    result = efficiency_momentum_score([100, 102, 104, 106, 108], lookback=4)
    expected_return = math.log(108 / 100)
    assert result["path_return"] == pytest.approx(expected_return)
    assert result["efficiency_ratio"] == pytest.approx(1.0)
    assert result["score"] == pytest.approx(expected_return)


def test_m3b_choppy_path_penalizes_the_same_endpoint_return():
    smooth = efficiency_momentum_score([100, 102, 104, 106, 108], lookback=4)
    choppy = efficiency_momentum_score([100, 110, 95, 112, 108], lookback=4)
    assert choppy["path_return"] == pytest.approx(smooth["path_return"])
    assert 0 < choppy["efficiency_ratio"] < 1
    assert choppy["score"] < smooth["score"]


def test_m3b_preserves_direction_and_handles_flat_path():
    down = efficiency_momentum_score([108, 106, 104, 102, 100], lookback=4)
    flat = efficiency_momentum_score([100, 100, 100, 100, 100], lookback=4)
    assert down["efficiency_ratio"] == pytest.approx(1.0)
    assert down["score"] < 0
    assert flat == {"path_return": 0.0, "efficiency_ratio": 0.0, "score": 0.0}


def test_rank_momentum_has_deterministic_code_tie_break():
    assert rank_momentum({"B": 0.1, "A": 0.1, "C": 0.2}) == [
        ("C", 0.2),
        ("A", 0.1),
        ("B", 0.1),
    ]
    assert top1_gap({"B": 0.1, "A": 0.1, "C": 0.2}) == pytest.approx(0.1)


def test_trend_outcome_requires_return_and_controls_adverse_excursion():
    result = trend_outcome([100, 98, 102], round_trip_cost=0.014, min_net_return=0.0, max_mae=-0.05)
    assert result["gross_return"] == pytest.approx(0.02)
    assert result["net_return"] == pytest.approx(0.006)
    assert result["mae"] == pytest.approx(-0.02)
    assert result["success"] is True


def test_trend_outcome_rejects_a_deep_drawdown_even_when_return_is_positive():
    result = trend_outcome([100, 90, 106], round_trip_cost=0.0014, min_net_return=0.01, max_mae=-0.05)
    assert result["success"] is False


def test_safe_buy_target_reserves_costs_for_a_nominal_full_investment():
    target = safe_buy_target_value(100000.0, 0.0, 100000.0)
    assert target < 100000.0
    assert target == pytest.approx(99925.052464, rel=1e-6)


def test_m1_keeps_positive_top1():
    result = absolute_momentum_target({"A": 0.12, "CASH": 0.01, "B": -0.02}, "CASH")
    assert result["decision"] == "top1"
    assert result["target"] == {"A": 1.0}


def test_m1_moves_to_cash_when_top1_is_negative():
    result = absolute_momentum_target({"A": -0.03, "CASH": -0.001, "B": -0.02}, "CASH")
    assert result["absolute_pass"] is False
    assert result["decision"] == "cash_filter"
    assert result["target"] == {"CASH": 1.0}


def test_m1_stays_in_cash_when_cash_security_is_unavailable():
    result = absolute_momentum_target({"A": -0.03, "B": -0.02}, "CASH")
    assert result["decision"] == "cash_unavailable"
    assert result["target"] == {}


def test_m2_keeps_top1_when_long_and_recent_momentum_are_positive():
    result = recent_confirmation_target(
        {"A": 0.12, "CASH": 0.01, "B": 0.02},
        {"A": 0.03, "CASH": 0.002, "B": -0.01},
        "CASH",
    )
    assert result["decision"] == "top1"
    assert result["target"] == {"A": 1.0}


def test_m2_moves_to_cash_when_recent_momentum_turns_negative():
    result = recent_confirmation_target(
        {"A": 0.12, "CASH": 0.01, "B": 0.02},
        {"A": -0.03, "CASH": 0.002, "B": 0.01},
        "CASH",
    )
    assert result["absolute_pass"] is True
    assert result["recent_pass"] is False
    assert result["decision"] == "recent_filter"
    assert result["target"] == {"CASH": 1.0}


def test_m2_holds_cash_when_cash_is_already_top1():
    result = recent_confirmation_target(
        {"A": -0.02, "CASH": 0.01, "B": 0.0},
        {"A": -0.03, "CASH": 0.002, "B": -0.01},
        "CASH",
    )
    assert result["decision"] == "cash_top1"
    assert result["target"] == {"CASH": 1.0}
