from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "step03_accounting_engine.py"
SPEC = importlib.util.spec_from_file_location("step03_accounting_engine", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
engine_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = engine_module
SPEC.loader.exec_module(engine_module)

AccountingEngine = engine_module.AccountingEngine
Bar = engine_module.Bar


def test_signal_after_close_executes_next_day_open() -> None:
    engine = AccountingEngine(initial_cash=1_000_000)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 1.0})

    assert engine.orders == []
    day = engine.process_day("2024-01-03", {"A": Bar(open=10, close=11)})

    assert engine.orders[0].order_date == "2024-01-03"
    assert engine.orders[0].side == "buy"
    assert engine.orders[0].filled_shares == 99_900
    expected_cash = 1_000_000 - 99_900 * 10.005 - max(5, 99_900 * 10.005 * 0.0002)
    assert day.cash == pytest.approx(expected_cash)
    assert day.total_value == pytest.approx(expected_cash + 99_900 * 11)


def test_non_rebalance_day_has_no_implicit_orders() -> None:
    engine = AccountingEngine(initial_cash=100_000)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 0.5})
    engine.process_day("2024-01-03", {"A": Bar(open=10, close=12)})
    count = len(engine.orders)

    engine.process_day("2024-01-04", {"A": Bar(open=9, close=8)})

    assert len(engine.orders) == count


def test_minimum_commission_and_lot_rounding() -> None:
    engine = AccountingEngine(initial_cash=10_000)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 0.1})
    engine.process_day("2024-01-03", {"A": Bar(open=10, close=10)})

    order = engine.orders[0]
    assert order.filled_shares == 100
    assert order.fee == 5
    assert order.fill_price == pytest.approx(10.005)
    assert engine.positions["A"] % 100 == 0


def test_switch_sells_before_buying_and_cash_never_negative() -> None:
    engine = AccountingEngine(initial_cash=100_000)
    day1 = {"A": Bar(open=10, close=10), "B": Bar(open=20, close=20)}
    engine.process_day("2024-01-02", day1)
    engine.submit_signal("2024-01-02", {"A": 0.8})
    engine.process_day("2024-01-03", day1)
    engine.submit_signal("2024-01-03", {"B": 0.8})

    engine.process_day("2024-01-04", day1)

    switch_orders = [order for order in engine.orders if order.order_date == "2024-01-04"]
    assert [order.side for order in switch_orders] == ["sell", "buy"]
    assert engine.cash >= 0
    assert "A" not in engine.positions
    assert engine.positions["B"] > 0


def test_blocked_order_retries_without_duplicate_fill() -> None:
    engine = AccountingEngine(initial_cash=100_000, max_retry_days=3)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 0.5})
    engine.process_day("2024-01-03", {"A": Bar(open=10, close=10, can_buy=False)})
    engine.process_day("2024-01-04", {"A": Bar(open=10, close=10, can_buy=False)})
    engine.process_day("2024-01-05", {"A": Bar(open=10, close=10, can_buy=True)})

    filled = [order for order in engine.orders if order.status in {"filled", "partial"}]
    assert len(filled) == 1
    assert filled[0].order_date == "2024-01-05"
    assert engine.positions["A"] == filled[0].filled_shares
    assert engine.pending is None


def test_retry_limit_cancels_unfilled_order() -> None:
    engine = AccountingEngine(initial_cash=100_000, max_retry_days=3)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 0.5})
    for date in ("2024-01-03", "2024-01-04", "2024-01-05"):
        engine.process_day(date, {"A": Bar(open=10, close=10, can_buy=False)})

    assert "A" not in engine.positions
    assert engine.pending is None
    assert engine.orders[-1].status == "canceled"
    assert engine.orders[-1].reason == "retry_limit"


def test_missing_open_never_uses_future_price() -> None:
    engine = AccountingEngine(initial_cash=100_000, max_retry_days=2)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 0.5})
    engine.process_day("2024-01-03", {"A": Bar(open=None, close=100)})

    assert engine.positions == {}
    assert engine.orders[-1].reason == "missing_open"
    engine.process_day("2024-01-04", {"A": Bar(open=12, close=12)})
    assert engine.orders[-2].raw_open is None
    assert engine.orders[-1].fill_price == pytest.approx(12.006)


def test_split_and_dividend_preserve_expected_value() -> None:
    engine = AccountingEngine(
        initial_cash=10_005.5,
        commission_rate=0,
        minimum_commission=0,
        slippage_rate=0,
    )
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 1.0})
    engine.process_day("2024-01-03", {"A": Bar(open=10, close=10)})
    before = engine.daily[-1].total_value

    after = engine.process_day(
        "2024-01-04", {"A": Bar(open=4.5, close=4.5, split_ratio=2, cash_dividend=0.5)}
    )

    assert engine.positions["A"] == 2_000
    assert after.total_value == pytest.approx(before)


def test_manual_round_trip_matches_independent_formula_to_one_cent() -> None:
    engine = AccountingEngine(initial_cash=100_000)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 0.5})
    engine.process_day("2024-01-03", {"A": Bar(open=10, close=11)})
    shares = engine.positions["A"]
    buy_price = 10 * 1.0005
    buy_fee = max(5, shares * buy_price * 0.0002)
    expected_cash_after_buy = 100_000 - shares * buy_price - buy_fee

    engine.submit_signal("2024-01-03", {})
    result = engine.process_day("2024-01-04", {"A": Bar(open=12, close=12)})
    sell_price = 12 * 0.9995
    sell_fee = max(5, shares * sell_price * 0.0002)
    independent_total = expected_cash_after_buy + shares * sell_price - sell_fee

    assert round(result.total_value - independent_total, 2) == 0


def test_invalid_target_weights_are_rejected() -> None:
    engine = AccountingEngine()
    with pytest.raises(ValueError):
        engine.submit_signal("2024-01-02", {"A": 0.6, "B": 0.5})
    with pytest.raises(ValueError):
        engine.submit_signal("2024-01-02", {"A": -0.1})


def test_partial_buy_keeps_remaining_target_for_retry() -> None:
    engine = AccountingEngine(initial_cash=100_000, max_retry_days=3)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 0.5})

    first = engine.process_day(
        "2024-01-03", {"A": Bar(open=10, close=10, max_buy_shares=717)}
    )
    assert first.positions["A"] == 717
    assert engine.pending is not None

    second = engine.process_day("2024-01-04", {"A": Bar(open=10, close=10)})
    assert second.positions["A"] == 4_917
    assert engine.pending is None
    assert [order.filled_shares for order in engine.orders if order.side == "buy"] == [717, 4_200]


def test_partial_sell_retries_and_clears_odd_lot_residual() -> None:
    engine = AccountingEngine(initial_cash=100_000, max_retry_days=3)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 0.5})
    engine.process_day("2024-01-03", {"A": Bar(open=10, close=10)})
    shares = engine.positions["A"]

    engine.submit_signal("2024-01-03", {})
    engine.process_day("2024-01-04", {"A": Bar(open=10, close=10, max_sell_shares=shares - 22)})
    assert engine.positions["A"] == 22
    assert engine.pending is not None

    engine.process_day("2024-01-05", {"A": Bar(open=10, close=10)})
    assert engine.positions == {}
    assert engine.pending is None
    assert engine.orders[-1].side == "sell"
    assert engine.orders[-1].requested_shares == 22


def test_partial_signal_expires_after_three_retry_days_without_duplicate_orders() -> None:
    engine = AccountingEngine(initial_cash=100_000, max_retry_days=3)
    engine.process_day("2024-01-02", {"A": Bar(open=10, close=10)})
    engine.submit_signal("2024-01-02", {"A": 0.5})
    engine.process_day("2024-01-03", {"A": Bar(open=10, close=10, max_buy_shares=717)})
    assert engine.pending is not None

    blocked = Bar(open=10, close=10, can_buy=False)
    engine.process_day("2024-01-04", {"A": blocked})
    engine.process_day("2024-01-05", {"A": blocked})
    engine.process_day("2024-01-06", {"A": blocked})

    assert engine.pending is None
    assert engine.positions["A"] == 717
    assert engine.orders[-1].status == "canceled"
    assert engine.orders[-1].reason == "retry_limit"
