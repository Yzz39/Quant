from pathlib import Path
import sys

import pandas as pd
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.performance_metrics import (
    annualized_volatility,
    drawdown_curve,
    max_drawdown,
    sharpe_ratio,
)

DATA_PATH = PROJECT_ROOT / "data" / "sample_etf_daily_long.csv"
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
df["strategy_drawdown"] = drawdown_curve(df["strategy_equity"])
df["benchmark_drawdown"] = drawdown_curve(df["benchmark_equity"])
strategy_annual_vol = annualized_volatility(df["strategy_ret"], periods_per_year=252)
benchmark_annual_vol = annualized_volatility(df["benchmark_ret"], periods_per_year=252)
strategy_sharpe = sharpe_ratio(df["strategy_ret"], periods_per_year=252)
benchmark_sharpe = sharpe_ratio(df["benchmark_ret"], periods_per_year=252)
assert df["position"].equals(df["signal"].shift(1).fillna(False).astype(bool))
assert df["strategy_equity"].notna().all()
assert df["benchmark_equity"].notna().all()
assert df["strategy_drawdown"].notna().all()
assert df["benchmark_drawdown"].notna().all()
assert (df["strategy_drawdown"] <= 0).all()
assert (df["benchmark_drawdown"] <= 0).all()
print("VERIFY_OK")
print("rows", len(df))
print("strategy_equity_last", round(float(df["strategy_equity"].iloc[-1]), 6))
print("benchmark_equity_last", round(float(df["benchmark_equity"].iloc[-1]), 6))
print("strategy_max_drawdown", round(float(max_drawdown(df["strategy_equity"])), 6))
print("benchmark_max_drawdown", round(float(max_drawdown(df["benchmark_equity"])), 6))
print("strategy_annual_volatility", round(float(strategy_annual_vol), 6))
print("benchmark_annual_volatility", round(float(benchmark_annual_vol), 6))
print("strategy_sharpe", round(float(strategy_sharpe), 6))
print("benchmark_sharpe", round(float(benchmark_sharpe), 6))
print("strategy_drawdown_last", round(float(df["strategy_drawdown"].iloc[-1]), 6))
