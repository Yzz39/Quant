import pytest

from scripts.step04_momentum_logic import (
    momentum_score,
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
