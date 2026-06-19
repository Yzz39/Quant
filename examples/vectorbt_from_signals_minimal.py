import pandas as pd
import vectorbt as vbt

price = pd.Series(
    [100.0, 102.0, 101.0, 105.0, 107.0, 106.0],
    index=pd.date_range("2026-01-01", periods=6, freq="D"),
    name="close",
)

entries = pd.Series(
    [True, False, False, False, False, False],
    index=price.index,
    name="entries",
)
exits = pd.Series(
    [False, False, False, False, True, False],
    index=price.index,
    name="exits",
)

portfolio = vbt.Portfolio.from_signals(
    close=price,
    entries=entries,
    exits=exits,
    init_cash=10_000,
    fees=0.001,
    freq="1D",
)

print("vectorbt", vbt.__version__)
print("total_return", portfolio.total_return())
print("final_value", portfolio.final_value())
print("orders")
print(portfolio.orders.records_readable)
