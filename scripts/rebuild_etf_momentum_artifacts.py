from pathlib import Path

import pandas as pd

base = Path(r"D:/Quant")
price_path = base / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
meta_path = base / "data" / "etf_momentum_universe.csv"
quality_path = base / "outputs" / "etf_momentum_data_quality.csv"
wide_path = base / "data" / "etf_momentum_close_wide_qfq.csv"
missing_path = base / "data" / "etf_momentum_close_wide_qfq_missing_report.csv"
pool_path = base / "data" / "etf_momentum_candidate_pool.csv"
selected_path = base / "data" / "etf_momentum_candidate_pool_selected.csv"

price = pd.read_csv(price_path, dtype={"symbol": "string"}, parse_dates=["date"])
meta = pd.read_csv(meta_path, dtype={"symbol": "string", "secid": "string"})
price["symbol"] = price["symbol"].astype("string").str.strip()
price["close"] = pd.to_numeric(price["close"], errors="coerce")
price["amount"] = pd.to_numeric(price["amount"], errors="coerce")

stats = price.groupby("symbol").agg(rows=("date", "size"), start=("date", "min"), end=("date", "max")).reset_index()
meta = meta.drop(columns=[column for column in ["rows", "start", "end"] if column in meta.columns], errors="ignore").merge(stats, on="symbol", how="left")
meta["download_status"] = meta["rows"].notna().map(lambda ok: "ok" if ok else "failed")
meta["rows"] = meta["rows"].fillna(0).astype(int)
meta["start"] = pd.to_datetime(meta["start"]).dt.strftime("%Y-%m-%d")
meta["end"] = pd.to_datetime(meta["end"]).dt.strftime("%Y-%m-%d")
meta["adjust"] = "qfq"
meta["source"] = "eastmoney_push2his"
meta["eastmoney_fqt"] = 1
meta.to_csv(meta_path, index=False, encoding="utf-8-sig")

summary = (
    price.groupby("symbol", dropna=False)
    .agg(
        actual_name=("name", "last"),
        rows=("date", "size"),
        start=("date", "min"),
        end=("date", "max"),
        missing_close=("close", lambda values: int(values.isna().sum())),
        avg_amount=("amount", "mean"),
        min_amount=("amount", "min"),
        adjust_actual=("adjust", "last"),
        source_actual=("source", "last"),
    )
    .reset_index()
)
quality = meta.rename(columns={"name": "planned_name"}).merge(summary, on="symbol", how="left", suffixes=("_meta", ""))
quality["download_status"] = quality["rows"].notna().map(lambda ok: "ok" if ok else "failed")
quality["rows"] = quality["rows"].fillna(0).astype(int)
quality["missing_close"] = quality["missing_close"].fillna(0).astype(int)
quality["adjust"] = quality["adjust_actual"].fillna("qfq_planned_not_downloaded")
quality["source"] = quality["source_actual"].fillna("eastmoney_push2his_failed")
quality = quality[
    [
        "symbol",
        "planned_name",
        "bucket",
        "theme",
        "actual_name",
        "rows",
        "start",
        "end",
        "missing_close",
        "avg_amount",
        "min_amount",
        "adjust",
        "source",
        "download_status",
    ]
]
quality = quality.sort_values(["download_status", "bucket", "symbol"])
quality.to_csv(quality_path, index=False, encoding="utf-8-sig")

wide = price.pivot(index="date", columns="symbol", values="close").sort_index().sort_index(axis=1)
wide.index.name = "date"
wide.to_csv(wide_path, encoding="utf-8-sig", date_format="%Y-%m-%d")
missing = pd.DataFrame(
    {
        "symbol": wide.columns,
        "missing_count": wide.isna().sum().astype(int).values,
        "total_dates": len(wide),
        "missing_ratio": wide.isna().mean().values,
        "first_valid_date": [wide[column].first_valid_index() for column in wide.columns],
        "last_valid_date": [wide[column].last_valid_index() for column in wide.columns],
    }
)
missing["first_valid_date"] = pd.to_datetime(missing["first_valid_date"]).dt.strftime("%Y-%m-%d")
missing["last_valid_date"] = pd.to_datetime(missing["last_valid_date"]).dt.strftime("%Y-%m-%d")
missing.sort_values(["missing_count", "symbol"], ascending=[False, True]).to_csv(missing_path, index=False, encoding="utf-8-sig")

latest_window = 60
min_history_years = 3.0
min_avg_amount = 100_000_000
records = []
for symbol, group in price.groupby("symbol", sort=True):
    group = group.sort_values("date")
    first_date = group["date"].min()
    last_date = group["date"].max()
    history_years = (last_date - first_date).days / 365.25
    avg_amount_60d = group.tail(latest_window)["amount"].mean()
    bucket = str(group["bucket"].dropna().iloc[-1]) if group["bucket"].notna().any() else ""
    theme = str(group["theme"].dropna().iloc[-1]) if group["theme"].notna().any() else ""
    name = str(group["name"].dropna().iloc[-1]) if group["name"].notna().any() else ""
    reasons = []
    if bucket == "benchmark":
        role = "benchmark"
        status = "selected"
        reasons.append("作为宽基基准/对照组，不参与行业主题排名时可单独处理")
    elif bucket == "defensive":
        role = "defensive_asset"
        status = "selected"
        reasons.append("作为防御资产/避险腿，可用于股债切换或空仓替代")
    elif bucket == "sector":
        role = "sector_rotation"
        if history_years >= min_history_years and avg_amount_60d >= min_avg_amount:
            status = "selected"
            reasons.append("行业/主题 ETF，历史长度与近期流动性满足动量候选池要求")
        elif history_years < min_history_years:
            status = "watchlist"
            reasons.append(f"上市/可用历史约 {history_years:.1f} 年，暂低于 {min_history_years:.1f} 年要求")
        else:
            status = "watchlist"
            reasons.append(f"近 {latest_window} 日平均成交额约 {avg_amount_60d:,.0f} 元，低于 {min_avg_amount:,.0f} 元阈值")
    else:
        role = "unknown"
        status = "excluded"
        reasons.append("bucket 未识别，需人工确认资产类型后再纳入")
    records.append(
        {
            "symbol": symbol,
            "name": name,
            "bucket": bucket,
            "theme": theme,
            "role": role,
            "candidate_status": status,
            "first_date": first_date.strftime("%Y-%m-%d"),
            "last_date": last_date.strftime("%Y-%m-%d"),
            "history_years": round(history_years, 2),
            "rows": int(len(group)),
            "avg_amount_60d": round(float(avg_amount_60d), 2),
            "latest_amount": round(float(group["amount"].iloc[-1]), 2),
            "missing_close_count_long": int(group["close"].isna().sum()),
            "screening_reason": "；".join(reasons),
        }
    )
pool = pd.DataFrame(records)
pool["status_order"] = pool["candidate_status"].map({"selected": 0, "watchlist": 1, "excluded": 2}).fillna(9)
pool = pool.sort_values(["status_order", "role", "symbol"]).drop(columns="status_order")
pool.to_csv(pool_path, index=False, encoding="utf-8-sig")
pool[pool["candidate_status"].eq("selected")].to_csv(selected_path, index=False, encoding="utf-8-sig")

print("price_rows", len(price), "symbols", price["symbol"].nunique())
print("universe_status")
print(meta["download_status"].value_counts().to_string())
print("quality_status")
print(quality["download_status"].value_counts().to_string())
print("wide_shape", wide.shape)
print("candidate_status")
print(pool["candidate_status"].value_counts().to_string())
print("remaining_failed")
print(meta[meta["download_status"].eq("failed")][["symbol", "name", "bucket", "theme"]].to_string(index=False))
