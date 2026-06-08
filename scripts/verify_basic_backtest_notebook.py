from pathlib import Path
import pandas as pd
import numpy as np
DATA_PATH = Path("sample_etf_daily_long.csv")
df = pd.read_csv(DATA_PATH)
required_cols = ["date", "open", "high", "low", "close", "volume"]
missing_cols = [c for c in required_cols if c not in df.columns]
assert not missing_cols, f"缺失必要字段: {missing_cols}"
df["date"] = pd.to_datetime(df["date"], errors="coerce")
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
if "amount" in df.columns:
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
df = df.sort_values("date").reset_index(drop=True)
assert df["date"].notna().all()
assert df["date"].is_monotonic_increasing
assert df["date"].duplicated().sum() == 0
assert df[required_cols].isna().sum().sum() == 0
bad_ohlc = df[(df["high"] < df["low"]) | (df["high"] < df["open"]) | (df["high"] < df["close"]) | (df["low"] > df["open"]) | (df["low"] > df["close"])]
assert len(bad_ohlc) == 0
assert not (df[["open", "high", "low", "close"]] <= 0).any(axis=None)
df["ret"] = df["close"].pct_change()
df["ma20"] = df["close"].rolling(20).mean()
df["ma60"] = df["close"].rolling(60).mean()
df["signal"] = df["close"] > df["ma20"]
df["position"] = df["signal"].shift(1).fillna(False).astype(bool)
df["strategy_ret"] = (df["position"].astype(int) * df["ret"]).fillna(0)
df["benchmark_ret"] = df["ret"].fillna(0)
df["strategy_equity"] = (1 + df["strategy_ret"]).cumprod()
df["benchmark_equity"] = (1 + df["benchmark_ret"]).cumprod()
def max_drawdown(equity):
    running_max = equity.cummax()
    return (equity / running_max - 1).min()
assert df["position"].equals(df["signal"].shift(1).fillna(False).astype(bool))
assert df["strategy_equity"].notna().all()
assert df["benchmark_equity"].notna().all()
print("VERIFY_OK")
print("rows", len(df))
print("strategy_equity_last", round(float(df["strategy_equity"].iloc[-1]), 6))
print("benchmark_equity_last", round(float(df["benchmark_equity"].iloc[-1]), 6))
print("strategy_max_drawdown", round(float(max_drawdown(df["strategy_equity"])), 6))
