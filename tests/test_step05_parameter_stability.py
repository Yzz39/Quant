import ast
import math
from pathlib import Path

import pytest

from scripts.step04_momentum_logic import (
    bias_trend_score,
    efficiency_momentum_score,
    huber_slope_r2_score,
    ols_slope_r2_score,
    wls_slope_r2_score,
)
from scripts.step05_parameter_stability import (
    MOMENTUM_LOOKBACKS,
    REBALANCE_INTERVALS,
    SIGNAL_MODES,
    is_rebalance_trade_day,
    parameter_grid,
    scaled_windows,
)


def test_step05_grid_contains_every_frozen_combination_once():
    grid = parameter_grid()
    assert len(grid) == 11 * 5 * 4 == 220
    assert len(
        {
            (row["run_mode"], row["lookback"], row["rebalance_interval"])
            for row in grid
        }
    ) == len(grid)
    assert tuple(row["run_mode"] for row in grid[::20]) == SIGNAL_MODES
    assert MOMENTUM_LOOKBACKS == (252, 126, 63, 31, 14)
    assert REBALANCE_INTERVALS == (20, 10, 5, 1)


@pytest.mark.parametrize(
    ("lookback", "recent", "ma_window", "trend_points"),
    [
        (252, 42, 180, 50),
        (126, 21, 90, 25),
        (63, 11, 45, 13),
        (31, 5, 22, 6),
        (14, 2, 10, 3),
    ],
)
def test_step05_subwindows_are_frozen_and_fit_main_window(
    lookback, recent, ma_window, trend_points
):
    result = scaled_windows(lookback)
    assert result == {
        "recent_lookback": recent,
        "bias_ma_window": ma_window,
        "bias_trend_points": trend_points,
    }
    assert recent <= lookback
    assert ma_window + trend_points - 1 <= lookback + 1


def test_step05_rebalance_phase_uses_nth_trading_day_from_start():
    assert [
        day for day in range(1, 41) if is_rebalance_trade_day(day, 20)
    ] == [20, 40]
    assert [day for day in range(1, 12) if is_rebalance_trade_day(day, 5)] == [5, 10]
    assert all(is_rebalance_trade_day(day, 1) for day in range(1, 12))


def test_step05_helpers_reject_unregistered_parameters():
    with pytest.raises(ValueError):
        scaled_windows(30)
    with pytest.raises(ValueError):
        is_rebalance_trade_day(0, 5)
    with pytest.raises(ValueError):
        is_rebalance_trade_day(5, 2)


@pytest.mark.parametrize("lookback", MOMENTUM_LOOKBACKS)
def test_every_factor_family_accepts_each_frozen_window(lookback):
    prices = [100.0 * 1.002**index for index in range(lookback + 1)]
    windows = scaled_windows(lookback)
    assert ols_slope_r2_score(prices, lookback)["score"] > 0
    assert wls_slope_r2_score(prices, lookback)["score"] > 0
    assert huber_slope_r2_score(prices, lookback)["score"] > 0
    assert efficiency_momentum_score(prices, lookback)["score"] > 0
    bias_score = bias_trend_score(
        prices,
        lookback=lookback,
        ma_window=windows["bias_ma_window"],
        trend_points=windows["bias_trend_points"],
    )["score"]
    assert math.isfinite(bias_score)


def test_step05_joinquant_script_defaults_to_first_grid_cell():
    script = Path(__file__).resolve().parents[1] / "step05_joinquant_parameter_stability.py"
    source = script.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"RUN_MODE", "LOOKBACK", "REBALANCE_INTERVAL"}
    }
    assert assignments == {
        "RUN_MODE": "momentum",
        "LOOKBACK": 252,
        "REBALANCE_INTERVAL": 20,
    }
    assert "if today < TRAIN_END and _is_rebalance_day(today):" in source
    assert "ma_window=BIAS_MA_WINDOW" in source
    assert "trend_points=BIAS_TREND_POINTS" in source
    assert "S05_CONFIG" in source
