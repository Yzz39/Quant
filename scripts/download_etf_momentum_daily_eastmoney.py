from __future__ import annotations

import json
import random
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / "data"
OUTPUT_PATH = DATA_DIR / "etf_momentum_daily_eastmoney_qfq.csv"
META_PATH = DATA_DIR / "etf_momentum_universe.csv"
REPORT_PATH = BASE / "outputs" / "etf_momentum_data_report.md"

START_DATE = "20150101"
END_DATE = "20500101"
ADJUST_FLAG = "qfq"
EASTMONEY_FQT = "1"  # Eastmoney K-line fqt=1, project convention: 前复权 qfq.
REQUEST_DELAY_SECONDS = 1.2

ETF_CONFIG = [
    # 行业/板块轮动核心池
    {"symbol": "512880", "secid": "1.512880", "name": "证券ETF", "bucket": "sector", "theme": "证券"},
    {"symbol": "512800", "secid": "1.512800", "name": "银行ETF", "bucket": "sector", "theme": "银行"},
    {"symbol": "512690", "secid": "1.512690", "name": "酒ETF", "bucket": "sector", "theme": "白酒/酒"},
    {"symbol": "512010", "secid": "1.512010", "name": "医药ETF", "bucket": "sector", "theme": "医药"},
    {"symbol": "512170", "secid": "1.512170", "name": "医疗ETF", "bucket": "sector", "theme": "医疗"},
    {"symbol": "512480", "secid": "1.512480", "name": "半导体ETF", "bucket": "sector", "theme": "半导体"},
    {"symbol": "515030", "secid": "1.515030", "name": "新能源车ETF", "bucket": "sector", "theme": "新能源车"},
    {"symbol": "515790", "secid": "1.515790", "name": "光伏ETF", "bucket": "sector", "theme": "光伏"},
    {"symbol": "512660", "secid": "1.512660", "name": "军工ETF", "bucket": "sector", "theme": "军工"},
    {"symbol": "512400", "secid": "1.512400", "name": "有色金属ETF", "bucket": "sector", "theme": "有色金属"},
    {"symbol": "515220", "secid": "1.515220", "name": "煤炭ETF", "bucket": "sector", "theme": "煤炭"},
    {"symbol": "512980", "secid": "1.512980", "name": "传媒ETF", "bucket": "sector", "theme": "传媒"},
    {"symbol": "515230", "secid": "1.515230", "name": "软件ETF", "bucket": "sector", "theme": "软件"},
    {"symbol": "159995", "secid": "0.159995", "name": "芯片ETF", "bucket": "sector", "theme": "芯片"},
    {"symbol": "159819", "secid": "0.159819", "name": "人工智能ETF", "bucket": "sector", "theme": "人工智能"},
    {"symbol": "159928", "secid": "0.159928", "name": "消费ETF", "bucket": "sector", "theme": "消费"},
    {"symbol": "159996", "secid": "0.159996", "name": "家电ETF", "bucket": "sector", "theme": "家电"},
    {"symbol": "159865", "secid": "0.159865", "name": "养殖ETF", "bucket": "sector", "theme": "养殖"},
    {"symbol": "159825", "secid": "0.159825", "name": "农业ETF", "bucket": "sector", "theme": "农业"},
    # 防御资产池
    {"symbol": "511010", "secid": "1.511010", "name": "国债ETF", "bucket": "defensive", "theme": "国债"},
    {"symbol": "511260", "secid": "1.511260", "name": "十年国债ETF", "bucket": "defensive", "theme": "十年国债"},
    {"symbol": "511880", "secid": "1.511880", "name": "银华日利ETF", "bucket": "defensive", "theme": "货币/现金"},
    {"symbol": "518880", "secid": "1.518880", "name": "黄金ETF", "bucket": "defensive", "theme": "黄金"},
    # 宽基基准池：用于对照，不作为板块轮动主角
    {"symbol": "510300", "secid": "1.510300", "name": "沪深300ETF", "bucket": "benchmark", "theme": "沪深300"},
    {"symbol": "510500", "secid": "1.510500", "name": "中证500ETF", "bucket": "benchmark", "theme": "中证500"},
    {"symbol": "159915", "secid": "0.159915", "name": "创业板ETF", "bucket": "benchmark", "theme": "创业板"},
]


def fetch_eastmoney_daily(secid: str) -> dict:
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": EASTMONEY_FQT,
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
            f"User-Agent: {headers['User-Agent']}",
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
        raise RuntimeError(f"Eastmoney returned invalid response for {secid}: {payload[:300]}")
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
                "bucket": config["bucket"],
                "theme": config["theme"],
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
                "source": "eastmoney_push2his",
                "adjust": ADJUST_FLAG,
                "eastmoney_fqt": EASTMONEY_FQT,
            }
        )
    return pd.DataFrame(rows)


def make_report(df: pd.DataFrame, failed: list[tuple[dict, str]]) -> str:
    summary = (
        df.groupby(["bucket", "symbol", "name", "theme"], dropna=False)
        .agg(
            rows=("date", "size"),
            start=("date", "min"),
            end=("date", "max"),
            first_close=("close", "first"),
            last_close=("close", "last"),
            avg_amount=("amount", "mean"),
            min_amount=("amount", "min"),
            missing_close=("close", lambda s: int(s.isna().sum())),
        )
        .reset_index()
        .sort_values(["bucket", "symbol"])
    )

    lines = [
        "# ETF 动量轮动历史价格数据下载报告",
        "",
        "## 数据文件",
        "",
        f"- 价格数据：`{OUTPUT_PATH.as_posix()}`",
        f"- 候选池元数据：`{META_PATH.as_posix()}`",
        "",
        "## 复权口径确认",
        "",
        "- 数据源：东方财富 push2his K 线接口。",
        "- 接口参数：`klt=101` 日线，`fqt=1`。",
        "- 项目口径：`adjust=qfq`，即前复权。",
        "- 用途：用于收益率、动量排序、均线等历史价格计算。",
        "- 注意：ETF 通常无印花税；复权用于处理分红等造成的价格跳变，但仍应在正式回测前做异常值检查。",
        "",
        "## 候选池分层",
        "",
        "- `sector`：行业/板块轮动主池。",
        "- `defensive`：国债、货币、黄金等防御资产。",
        "- `benchmark`：宽基基准，用于对照或市场状态过滤，不作为板块轮动主角。",
        "",
        "## 下载概况",
        "",
        f"- 成功 ETF 数：{summary['symbol'].nunique() if not summary.empty else 0}",
        f"- 总行数：{len(df)}",
        f"- 样本起始：{df['date'].min().date() if not df.empty else ''}",
        f"- 样本结束：{df['date'].max().date() if not df.empty else ''}",
        "",
    ]

    if failed:
        lines.extend(["## 下载失败", ""])
        for config, err in failed:
            lines.append(f"- `{config['symbol']}` {config['name']}：{err}")
        lines.append("")

    lines.extend(
        [
            "## 单品种数据摘要",
            "",
            "| 分层 | 代码 | 名称 | 主题 | 行数 | 起始 | 结束 | 首日收盘 | 末日收盘 | 平均成交额 | 最低成交额 | 缺失收盘 |",
            "|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.bucket} | {row.symbol} | {row.name} | {row.theme} | {row.rows} | "
            f"{row.start.date()} | {row.end.date()} | {row.first_close:.4f} | {row.last_close:.4f} | "
            f"{row.avg_amount:,.0f} | {row.min_amount:,.0f} | {row.missing_close} |"
        )

    return "\n".join(lines) + "\n"


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    frames = []
    existing_symbols: set[str] = set()
    if OUTPUT_PATH.exists():
        existing = pd.read_csv(OUTPUT_PATH, parse_dates=["date"], dtype={"symbol": "string"})
        if not existing.empty:
            frames.append(existing)
            existing_symbols = set(existing["symbol"].astype(str).unique())
            print(f"Loaded existing data: {len(existing)} rows; {len(existing_symbols)} ETFs")

    failed: list[tuple[dict, str]] = []
    for config in ETF_CONFIG:
        if config["symbol"] in existing_symbols:
            print(f"SKIP {config['symbol']} {config['name']}: already downloaded")
            continue
        try:
            data = fetch_eastmoney_daily(config["secid"])
            frame = parse_klines(config, data)
            if frame.empty:
                raise RuntimeError("empty kline list")
            frames.append(frame)
            print(f"OK {config['symbol']} {config['name']}: {len(frame)} rows")
            time.sleep(REQUEST_DELAY_SECONDS + random.random())
        except Exception as exc:
            failed.append((config, str(exc)))
            print(f"FAIL {config['symbol']} {config['name']}: {exc}")
            time.sleep(REQUEST_DELAY_SECONDS * 2 + random.random())

    if not frames:
        raise RuntimeError("No ETF data downloaded; refusing to create empty final files.")

    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(["symbol", "date"], keep="last")
    df = df.sort_values(["bucket", "symbol", "date"]).reset_index(drop=True)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    meta = pd.DataFrame(ETF_CONFIG)
    downloaded_symbols = set(df["symbol"].astype(str))
    meta["download_status"] = meta["symbol"].map(lambda x: "ok" if x in downloaded_symbols else "failed")
    meta["adjust"] = ADJUST_FLAG
    meta["source"] = "eastmoney_push2his"
    meta["eastmoney_fqt"] = EASTMONEY_FQT
    meta.to_csv(META_PATH, index=False, encoding="utf-8-sig")

    REPORT_PATH.write_text(make_report(df, failed), encoding="utf-8")

    print(f"Saved data: {OUTPUT_PATH}")
    print(f"Saved universe: {META_PATH}")
    print(f"Saved report: {REPORT_PATH}")
    print(f"Rows: {len(df)}; ETFs: {df['symbol'].nunique()}; failed: {len(failed)}")


if __name__ == "__main__":
    main()
