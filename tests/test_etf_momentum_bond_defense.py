from pathlib import Path
import sys

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from backtest_etf_momentum_bond_defense import (  # noqa: E402
    BOND_SYMBOL,
    choose_target_weights,
)


def test_top2_momentum_without_defense_is_equal_weight() -> None:
    momentum = pd.Series({"A": 0.10, "B": 0.30, "C": -0.05})
    next_open = pd.Series({"A": 1.0, "B": 1.0, "C": 1.0, BOND_SYMBOL: 100.0})

    weights, selected = choose_target_weights(
        momentum,
        0.20,
        ["A", "B", "C"],
        next_open,
        use_bond_defense=False,
    )

    assert selected == ["B", "A"]
    assert weights == {"B": 0.5, "A": 0.5}


def test_high_volatility_moves_twenty_percent_to_bond() -> None:
    momentum = pd.Series({"A": 0.10, "B": 0.30, "C": -0.05})
    next_open = pd.Series({"A": 1.0, "B": 1.0, "C": 1.0, BOND_SYMBOL: 100.0})

    weights, selected = choose_target_weights(
        momentum,
        0.30,
        ["A", "B", "C"],
        next_open,
        use_bond_defense=True,
    )

    assert selected == ["B", "A"]
    assert weights == {"B": 0.4, "A": 0.4, BOND_SYMBOL: 0.2}
    assert sum(weights.values()) == 1.0


def test_untradable_etf_is_not_selected() -> None:
    momentum = pd.Series({"A": 0.50, "B": 0.30, "C": 0.10})
    next_open = pd.Series({"A": float("nan"), "B": 1.0, "C": 1.0})

    weights, selected = choose_target_weights(
        momentum,
        0.10,
        ["A", "B", "C"],
        next_open,
        use_bond_defense=False,
    )

    assert selected == ["B", "C"]
    assert weights == {"B": 0.5, "C": 0.5}
