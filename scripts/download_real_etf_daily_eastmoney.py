from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

ETF_CONFIG = [
    {"symbol": "159915", "secid": "0.159915", "name": "创业板ETF易方达"},
    {"symbol": "510300", "secid": "1.510300", "name": "沪深300ETF"},
    {"symbol": "511010", "secid": "1.511010", "name": "国债ETF"},
]

OUTPUT_PATH = Path("data/real_etf_daily_eastmoney.csv")
START_DATE = "20150101"
END_DATE = "20500101"


def fetch_eastmoney_daily(secid: str) -> dict:
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": START_DATE,
        "end": END_DATE,
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urlencode(params)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://quote.eastmoney.com/",
        "Accept": "application/json,text/plain,*/*",
    }

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
            break
        except Exception as exc:
            last_error = exc
            time.sleep(1 + attempt)
    else:
        curl_command = [
            "curl",
            "-L",
            "--max-time",
            "45",
            "-H",
            headers["User-Agent"],
            "-H",
            f"Referer: {headers['Referer']}",
            url,
        ]
        try:
            completed = subprocess.run(
                curl_command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            payload = completed.stdout
        except Exception as exc:
            raise RuntimeError(f"Failed to download {secid}: {last_error}; curl fallback: {exc}") from exc

    result = json.loads(payload)
    if result.get("rc") != 0 or not result.get("data"):
        raise RuntimeError(f"Eastmoney returned invalid response for {secid}: {payload[:200]}")
    return result["data"]


def parse_klines(config: dict, data: dict) -> pd.DataFrame:
    rows = []
    for line in data.get("klines", []):
        fields = line.split(",")
        rows.append(
            {
                "date": fields[0],
                "symbol": config["symbol"],
                "name": data.get("name") or config["name"],
                "open": float(fields[1]),
                "close": float(fields[2]),
                "high": float(fields[3]),
                "low": float(fields[4]),
                "volume": float(fields[5]),
                "amount": float(fields[6]),
                "amplitude_pct": float(fields[7]),
                "pct_change": float(fields[8]),
                "change": float(fields[9]),
                "turnover_pct": float(fields[10]) if fields[10] != "-" else float("nan"),
                "source": "eastmoney",
                "adjust": "qfq",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    frames = []
    for config in ETF_CONFIG:
        data = fetch_eastmoney_daily(config["secid"])
        frame = parse_klines(config, data)
        if frame.empty:
            raise RuntimeError(f"No rows downloaded for {config['symbol']}")
        frames.append(frame)

    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"])
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"Saved: {OUTPUT_PATH}")
    print(f"Rows: {len(df)}")
    print(
        df.groupby(["symbol", "name"]).agg(
            rows=("date", "size"),
            start=("date", "min"),
            end=("date", "max"),
            first_close=("close", "first"),
            last_close=("close", "last"),
        ).to_string()
    )


if __name__ == "__main__":
    main()
