from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
MAIN = BASE / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
OLD = BASE / "data" / "real_etf_daily_eastmoney.csv"
META = {
    "159915": ("benchmark", "创业板"),
    "510300": ("benchmark", "沪深300"),
    "511010": ("defensive", "国债"),
}

main = pd.read_csv(MAIN, parse_dates=["date"], dtype={"symbol": "string"})
old = pd.read_csv(OLD, parse_dates=["date"], dtype={"symbol": "string"})
old = old[old["symbol"].isin(META.keys())].copy()
old["bucket"] = old["symbol"].map(lambda s: META[str(s)][0])
old["theme"] = old["symbol"].map(lambda s: META[str(s)][1])
old["source"] = "eastmoney_push2his_existing_project_file"
old["eastmoney_fqt"] = "1"
# Align columns. Older file does not have bucket/theme/eastmoney_fqt but is already project qfq data.
for col in main.columns:
    if col not in old.columns:
        old[col] = pd.NA
old = old[main.columns]
merged = pd.concat([main, old], ignore_index=True)
merged = merged.drop_duplicates(["symbol", "date"], keep="last")
merged = merged.sort_values(["bucket", "symbol", "date"]).reset_index(drop=True)
merged.to_csv(MAIN, index=False, encoding="utf-8-sig")
print(f"merged rows={len(merged)} etfs={merged['symbol'].nunique()}")
print(merged.groupby(["bucket", "symbol", "name"]).agg(rows=("date","size"), start=("date","min"), end=("date","max")).to_string())
