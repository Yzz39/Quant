import math

import pytest

from scripts.step04_momentum_logic import (
    efficiency_momentum_score,
    bias_trend_score,
    equal_rank_fusion,
    momentum_score,
    ols_slope_r2_score,
    wls_slope_r2_score,
    huber_slope_r2_score,
    absolute_momentum_target,
    rank_momentum,
    recent_confirmation_target,
    ranked_recent_target,
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


def test_m3d_perfect_exponential_trend_has_weighted_r2_one():
    prices = [100.0 * 1.02**index for index in range(5)]
    result = wls_slope_r2_score(prices, lookback=4)
    assert result["beta"] == pytest.approx(math.log(1.02))
    assert result["r_squared"] == pytest.approx(1.0)
    assert result["score"] == pytest.approx(math.log(1.02))


def test_m3d_recent_weights_change_a_non_linear_trend_and_validate_prices():
    prices = [100.0, 104.0, 108.0, 106.0, 105.0]
    ols = ols_slope_r2_score(prices, lookback=4)
    wls = wls_slope_r2_score(prices, lookback=4)
    assert wls["beta"] < ols["beta"]
    assert 0.0 <= wls["r_squared"] <= 1.0
    with pytest.raises(ValueError):
        wls_slope_r2_score([100.0, 101.0, 102.0], lookback=3)
    with pytest.raises(ValueError):
        wls_slope_r2_score([100.0, 101.0, 0.0, 102.0], lookback=3)


def test_m3e_perfect_exponential_trend_matches_ols_without_downweighting():
    prices = [100.0 * 1.02**index for index in range(9)]
    result = huber_slope_r2_score(prices, lookback=8)
    assert result["beta"] == pytest.approx(math.log(1.02))
    assert result["r_squared"] == pytest.approx(1.0)
    assert result["score"] == pytest.approx(math.log(1.02))
    assert result["downweighted"] == 0


def test_m3e_is_closer_than_ols_to_the_true_slope_with_one_outlier():
    true_beta = math.log(1.01)
    prices = [100.0 * 1.01**index for index in range(21)]
    prices[-2] *= 1.35
    ols = ols_slope_r2_score(prices, lookback=20)
    huber = huber_slope_r2_score(prices, lookback=20)
    assert abs(huber["beta"] - true_beta) < abs(ols["beta"] - true_beta)
    assert huber["downweighted"] >= 1
    assert 0.0 <= huber["r_squared"] <= 1.0


def test_m3e_keeps_robust_weights_when_final_mad_reaches_numerical_floor():
    true_beta = math.log(1.006)
    prices = [100.0 * 1.006**index for index in range(127)]
    prices[49] *= 1.25
    prices[93] *= 0.72
    result = huber_slope_r2_score(prices)
    assert result["beta"] == pytest.approx(true_beta, abs=1e-10)
    assert result["downweighted"] >= 2


def test_m3e_validates_prices_and_frozen_parameters():
    with pytest.raises(ValueError):
        huber_slope_r2_score([100.0, 101.0, 102.0], lookback=3)
    with pytest.raises(ValueError):
        huber_slope_r2_score([100.0, 101.0, 0.0, 102.0], lookback=3)
    with pytest.raises(ValueError):
        huber_slope_r2_score([100.0, 101.0, 102.0, 103.0], lookback=3, epsilon=0)


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


def test_m3c_rising_bias_has_positive_slope_and_flat_prices_are_flat():
    rising = [100.0] * 102 + [100.0 + index for index in range(25)]
    rising_result = bias_trend_score(rising)
    flat_result = bias_trend_score([100.0] * 127)
    assert rising_result["bias_slope"] > 0
    assert rising_result["score"] == rising_result["bias_slope"]
    assert flat_result["score"] == pytest.approx(0.0)


def test_m3c_uses_latest_25_bias_points_and_rejects_invalid_prices():
    prices = [80.0] * 13 + [100.0] * 114
    assert bias_trend_score(prices)["score"] == pytest.approx(0.0)
    with pytest.raises(ValueError):
        bias_trend_score([100.0] * 126)
    with pytest.raises(ValueError):
        bias_trend_score([100.0] * 126 + [0.0])


def test_m3f_equal_rank_fusion_uses_three_equal_votes_not_raw_scales():
    result = equal_rank_fusion(
        {
            "huber": {"A": 3.0, "B": 2.0, "C": 1.0},
            "efficiency": {"A": 200.0, "B": 300.0, "C": 100.0},
            "bias": {"A": 0.003, "B": 0.002, "C": 0.001},
        }
    )
    assert result["scores"] == pytest.approx({"A": 2.0 / 3.0, "B": 1.0 / 3.0, "C": -1.0})
    assert result["ranks"]["A"] == {"bias": 1, "efficiency": 2, "huber": 1}
    assert sum(result["scores"].values()) == pytest.approx(0.0)


def test_m3f_equal_rank_fusion_has_deterministic_ties_and_validates_inputs():
    tied = equal_rank_fusion({"huber": {"B": 1.0, "A": 1.0}})
    assert tied["ranks"] == {"A": {"huber": 1}, "B": {"huber": 2}}
    assert tied["scores"] == {"A": 1.0, "B": -1.0}
    equal_rank_sums = equal_rank_fusion(
        {
            "huber": {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0},
            "efficiency": {"B": 4.0, "C": 3.0, "A": 2.0, "D": 1.0},
            "bias": {"C": 4.0, "D": 3.0, "A": 2.0, "B": 1.0},
        }
    )
    assert equal_rank_sums["scores"]["A"] == equal_rank_sums["scores"]["B"]
    assert rank_momentum(equal_rank_sums["scores"])[1:3] == [
        ("A", equal_rank_sums["scores"]["A"]),
        ("B", equal_rank_sums["scores"]["B"]),
    ]
    with pytest.raises(ValueError):
        equal_rank_fusion({})
    with pytest.raises(ValueError):
        equal_rank_fusion({"huber": {"A": 1.0}, "bias": {"B": 1.0}})
    with pytest.raises(ValueError):
        equal_rank_fusion({"huber": {"A": float("nan")}})


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


def test_m2r_excludes_negative_recent_top1_and_selects_next_rank():
    result = ranked_recent_target(
        {"A": 0.12, "B": 0.08, "CASH": 0.01},
        {"A": -0.03, "B": 0.02, "CASH": 0.002},
        "CASH",
    )
    assert result["selected"] == "B"
    assert result["selected_rank"] == 2
    assert result["excluded"] == ["A"]
    assert result["decision"] == "ranked_recent_pass"
    assert result["target"] == {"B": 1.0}


def test_m2r_continues_past_multiple_failures_until_cash_rank():
    result = ranked_recent_target(
        {"A": 0.12, "B": 0.08, "CASH": 0.01, "C": -0.02},
        {"A": -0.03, "B": -0.01, "CASH": 0.002, "C": 0.04},
        "CASH",
    )
    assert result["selected"] == "CASH"
    assert result["selected_rank"] == 3
    assert result["excluded"] == ["A", "B"]
    assert result["decision"] == "cash_ranked"


def test_m2r_uses_cash_fallback_or_stays_empty_when_no_candidate_passes():
    with_cash = ranked_recent_target(
        {"A": -0.01, "CASH": -0.02},
        {"A": 0.03, "CASH": -0.001},
        "CASH",
    )
    without_cash = ranked_recent_target(
        {"A": -0.01, "B": -0.02},
        {"A": 0.03, "B": 0.02},
        "CASH",
    )
    assert with_cash["target"] == {"CASH": 1.0}
    assert with_cash["decision"] == "cash_ranked"
    assert without_cash["target"] == {}
    assert without_cash["decision"] == "cash_unavailable"
