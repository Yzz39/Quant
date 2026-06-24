import math
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.bt_minimal_equal_weight_portfolio import build_target_weights, run_minimal_backtest


def test_build_target_weights_applies_month_end_signal_on_next_trading_day():
    close = pd.DataFrame(
        {
            "A": [10.0, 11.0, 12.0, 13.0],
            "B": [20.0, 21.0, 22.0, 23.0],
        },
        index=pd.to_datetime(["2026-01-29", "2026-01-30", "2026-02-02", "2026-02-03"]),
    )
    decisions = pd.DataFrame(
        [
            {
                "signal_date": pd.Timestamp("2026-01-30"),
                "selected_symbols": "A|B",
            }
        ]
    )

    weights = build_target_weights(close, decisions)

    assert weights.loc[pd.Timestamp("2026-01-30")].sum() == 0.0
    assert weights.loc[pd.Timestamp("2026-02-02"), "A"] == 0.5
    assert weights.loc[pd.Timestamp("2026-02-02"), "B"] == 0.5


def test_run_minimal_backtest_uses_previous_day_weights_for_returns():
    close = pd.DataFrame(
        {"A": [100.0, 110.0, 121.0]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
    )
    target_weights = pd.DataFrame(
        {"A": [0.0, 1.0, 1.0]},
        index=close.index,
    )

    daily, _ = run_minimal_backtest(close, target_weights, one_way_cost_rate=0.0)

    assert daily.loc[1, "gross_return"] == 0.0
    assert math.isclose(daily.loc[2, "gross_return"], 0.1, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(daily.loc[2, "nav"], 1.1, rel_tol=0, abs_tol=1e-12)


def test_run_minimal_backtest_charges_cost_on_one_way_turnover():
    close = pd.DataFrame(
        {"A": [100.0, 100.0, 100.0]},
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
    )
    target_weights = pd.DataFrame(
        {"A": [0.0, 1.0, 0.0]},
        index=close.index,
    )

    daily, trades = run_minimal_backtest(close, target_weights, one_way_cost_rate=0.001)

    assert list(trades["one_way_turnover"]) == [1.0, 1.0]
    assert math.isclose(daily["cost"].sum(), 0.002, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(daily["nav"].iloc[-1], (1 - 0.001) * (1 - 0.001), rel_tol=0, abs_tol=1e-12)
