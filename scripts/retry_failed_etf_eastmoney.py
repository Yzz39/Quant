from __future__ import annotations

import json
import random
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / "data"
OUTPUT_PATH = DATA_DIR / "etf_momentum_daily_eastmoney_qfq.csv"
META_PATH = DATA_DIR / "etf_momentum_universe.csv"
QUALITY_PATH = BASE / "outputs" / "etf_momentum_data_quality.csv"
START_DATE = "20150101"
END_DATE = "20500101"
EASTMONEY_FQT = "1"
ADJUST_FLAG = "qfq"


def fetch_with_curl(secid: str, timeout: int = 60) -> dict:
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": EASTMONEY_FQT,
        "beg": START_DATE,
        "end": END_DATE,
        "lmt": "1000000",
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urlencode(params)
    headers = [
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36",
        "Referer: https://quote.eastmoney.com/",
        "Accept: application/json,text/plain,*/*",
        "Connection: close",
    ]
    cmd = ["curl", "-sS", "--http1.1", "--retry", "3", "--retry-delay", "3", "--connect-timeout", "20", "--max-time", str(timeout)]
    for h in headers:
        cmd += ["-H", h]
    cmd.append(url)
    completed = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=timeout + 10)
    if completed.returncode != 0:
        raise RuntimeError(f"curl exit {completed.returncode}: {completed.stderr.strip()[:300]}")
    payload = completed.stdout.strip()
    if not payload:
        raise RuntimeError("empty response")
    result = json.loads(payload)
    if result.get("rc") != 0 or not result.get("data"):
        raise RuntimeError(f"invalid response: {payload[:300]}")
    if not result["data"].get("klines"):
        raise RuntimeError("empty kline list")
    return result["data"]


def parse_klines(config: dict, data: dict) -> pd.DataFrame:
    rows = []
    for line in data.get("klines", []):
        f = line.split(",")
        rows.append({
            "date": f[0],
            "symbol": str(config["symbol"]),
            "name": data.get("name") or config["name"],
            "bucket": config["bucket"],
            "theme": config["theme"],
            "open": float(f[1]),
            "close": float(f[2]),
            "high": float(f[3]),
            "low": float(f[4]),
            "volume": float(f[5]),
            "amount": float(f[6]),
            "amplitude_pct": float(f[7]),
            "pct_change": float(f[8]),
            "change": float(f[9]),
            "turnover_pct": float(f[10]) if f[10] != "-" else float("nan"),
            "source": "eastmoney_push2his_retry",
            "adjust": ADJUST_FLAG,
            "eastmoney_fqt": EASTMONEY_FQT,
        })
    return pd.DataFrame(rows)


def rebuild_quality(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    summary = (df.groupby("symbol", dropna=False)
        .agg(actual_name=("name", "last"), rows=("date", "size"), start=("date", "min"), end=("date", "max"),
             missing_close=("close", lambda s: int(s.isna().sum())), avg_amount=("amount", "mean"), min_amount=("amount", "min"),
             source=("source", "last"), adjust=("adjust", "last"))
        .reset_index())
    q = meta.rename(columns={"name": "planned_name"}).merge(summary, on="symbol", how="left")
    q["download_status"] = q["rows"].notna().map(lambda x: "ok" if x else "failed")
    q["rows"] = q["rows"].fillna(0).astype(int)
    q["missing_close"] = q["missing_close"].fillna(0).astype(int)
    q["adjust"] = q["adjust_y"].fillna("qfq_planned_not_downloaded")
    q["source"] = q["source_y"].fillna("eastmoney_push2his_failed")
    q = q[["symbol", "planned_name", "bucket", "theme", "actual_name", "rows", "start", "end", "missing_close", "avg_amount", "min_amount", "adjust", "source", "download_status"]]
    return q.sort_values(["download_status", "bucket", "symbol"])


def main() -> None:
    meta = pd.read_csv(META_PATH, dtype={"symbol": "string", "secid": "string"})
    df = pd.read_csv(OUTPUT_PATH, dtype={"symbol": "string"}, parse_dates=["date"])
    existing = set(df["symbol"].astype(str).unique())
    targets = meta[~meta["symbol"].astype(str).isin(existing)].copy()
    print(f"Existing ETFs: {len(existing)}; retry targets: {len(targets)}")

    new_frames = []
    failures = []
    for rec in targets.to_dict("records"):
        symbol = str(rec["symbol"])
        secid = str(rec["secid"])
        name = rec["name"]
        ok = False
        for attempt in range(1, 5):
            try:
                print(f"TRY {symbol} {name} attempt={attempt}", flush=True)
                data = fetch_with_curl(secid, timeout=75)
                frame = parse_klines(rec, data)
                new_frames.append(frame)
                print(f"OK {symbol} {name}: {len(frame)} rows", flush=True)
                ok = True
                break
            except Exception as exc:
                err = str(exc)
                print(f"FAIL {symbol} {name} attempt={attempt}: {err}", flush=True)
                time.sleep(6 + attempt * 4 + random.random() * 3)
        if not ok:
            failures.append((symbol, name))
        time.sleep(4 + random.random() * 4)

    if new_frames:
        combined = pd.concat([df] + new_frames, ignore_index=True)
        combined["date"] = pd.to_datetime(combined["date"])
        combined["symbol"] = combined["symbol"].astype(str)
        combined = combined.drop_duplicates(["symbol", "date"], keep="last").sort_values(["bucket", "symbol", "date"])
        combined.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        df = combined

    downloaded = set(df["symbol"].astype(str).unique())
    meta["download_status"] = meta["symbol"].astype(str).map(lambda s: "ok" if s in downloaded else "failed")
    stats = df.groupby("symbol").agg(rows=("date", "size"), start=("date", "min"), end=("date", "max")).reset_index()
    meta = meta.drop(columns=[c for c in ["rows", "start", "end"] if c in meta.columns], errors="ignore").merge(stats, on="symbol", how="left")
    meta["rows"] = meta["rows"].fillna(0).astype(int)
    meta["start"] = pd.to_datetime(meta["start"]).dt.strftime("%Y-%m-%d")
    meta["end"] = pd.to_datetime(meta["end"]).dt.strftime("%Y-%m-%d")
    meta["adjust"] = ADJUST_FLAG
    meta["source"] = "eastmoney_push2his"
    meta["eastmoney_fqt"] = EASTMONEY_FQT
    meta.to_csv(META_PATH, index=False, encoding="utf-8-sig")

    quality = rebuild_quality(df, meta)
    QUALITY_PATH.parent.mkdir(parents=True, exist_ok=True)
    quality.to_csv(QUALITY_PATH, index=False, encoding="utf-8-sig")

    print(f"Saved {OUTPUT_PATH}")
    print(f"Saved {META_PATH}")
    print(f"Saved {QUALITY_PATH}")
    print(f"Rows: {len(df)}; ETFs: {df['symbol'].nunique()}; remaining_failed: {len(meta[meta['download_status'].eq('failed')])}")
    if failures:
        print("Still failed:", failures)


if __name__ == "__main__":
    main()
