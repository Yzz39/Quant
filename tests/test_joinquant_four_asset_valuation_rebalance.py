from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from joinquant_four_asset_valuation_rebalance import (  # noqa: E402
    BOND_ETF,
    EQUITY_ETF,
    GOLD_ETF,
    calculate_pe_percentile,
    target_weights,
    valuation_regime,
)


def test_pe_percentile_requires_warmup_and_uses_only_history() -> None:
    assert calculate_pe_percentile(12.0, [10.0, 20.0], 3) is None
    assert calculate_pe_percentile(15.0, [10.0, 20.0, 30.0], 3) == 100.0 / 3.0


def test_valuation_regime_boundaries() -> None:
    assert valuation_regime(None) == "neutral"
    assert valuation_regime(15.0) == "extreme_low"
    assert valuation_regime(30.0) == "low"
    assert valuation_regime(70.0) == "neutral"
    assert valuation_regime(70.01) == "high"


def test_base_experiment_is_fixed_four_asset_allocation() -> None:
    regime, weights = target_weights("FOUR_ASSET_BASE", 1.0)

    assert regime == "neutral"
    assert weights == {
        EQUITY_ETF: 0.25,
        BOND_ETF: 0.25,
        GOLD_ETF: 0.25,
        "cash": 0.25,
    }


def test_valuation_tilt_moves_only_equity_and_cash() -> None:
    expected = {
        10.0: ("extreme_low", 0.50, 0.00),
        20.0: ("low", 0.375, 0.125),
        50.0: ("neutral", 0.25, 0.25),
        80.0: ("high", 0.125, 0.375),
    }
    for percentile, (expected_regime, equity, cash) in expected.items():
        regime, weights = target_weights("VALUATION_TILT", percentile)
        assert regime == expected_regime
        assert weights[EQUITY_ETF] == equity
        assert weights[BOND_ETF] == 0.25
        assert weights[GOLD_ETF] == 0.25
        assert weights["cash"] == cash
        assert abs(sum(weights.values()) - 1.0) < 1e-12
