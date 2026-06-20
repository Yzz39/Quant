from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import DateOffset

BASE = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = BASE / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
DEFAULT_OUTPUT = BASE / "outputs" / "etf_single_momentum_returns.csv"
DEFAULT_REPORT = BASE / "outputs" / "etf_single_momentum_returns_report.md"


def parse_months(raw: str) -> list[int]:
    months = []
    for part in raw.split(","):
        value = int(part.strip())
        if value <= 0:
            raise ValueError("months must be positive")
        months.append(value)
    return sorted(set(months))


def latest_on_or_before(data: pd.DataFrame, target_date: pd.Timestamp) -> pd.Series | None:
    eligible = data[data["date"] <= target_date]
    if eligible.empty:
        return None
    return eligible.iloc[-1]


def compute_single_symbol_returns(symbol_df: pd.DataFrame, months_list: list[int]) -> list[dict]:
    symbol_df = symbol_df.sort_values("date").reset_index(drop=True)
    rows = []
    for current in symbol_df.itertuples(index=False):
        current_date = pd.Timestamp(current.date)
        current_close = float(current.close)
        for months in months_list:
            target_date = current_date - DateOffset(months=months)
            past = latest_on_or_before(symbol_df, target_date)
            if past is None or pd.isna(past.close) or past.close <= 0:
                past_date = pd.NaT
                past_close = pd.NA
                ret = pd.NA
                actual_days = pd.NA
                valid = False
            else:
                past_date = pd.Timestamp(past.date)
                past_close = float(past.close)
                ret = current_close / past_close - 1
                actual_days = (current_date - past_date).days
                valid = True
            rows.append(
                {
                    "date": current_date,
                    "symbol": current.symbol,
                    "name": current.name,
                    "bucket": current.bucket,
                    "theme": current.theme,
                    "months": months,
                    "lookback_target_date": target_date,
                    "lookback_actual_date": past_date,
                    "actual_calendar_days": actual_days,
                    "current_close": current_close,
                    "lookback_close": past_close,
                    "return_n_months": ret,
                    "valid": valid,
                    "adjust": current.adjust,
                    "source": current.source,
                }
            )
    return rows


def pct(value: float | pd.NA) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.2%}"


def make_report(result: pd.DataFrame, months_list: list[int], output_path: Path) -> str:
    latest_date = result["date"].max()
    latest = result[(result["date"] == latest_date) & result["valid"]].copy()
    latest = latest.sort_values(["months", "return_n_months"], ascending=[True, False])
    coverage = (
        result.groupby(["symbol", "name", "bucket", "theme", "months"], dropna=False)
        .agg(rows=("date", "size"), valid_rows=("valid", "sum"), start=("date", "min"), end=("date", "max"))
        .reset_index()
    )

    lines = [
        "# 单个 ETF 过去 N 个月收益率",
        "",
        "## 输出文件",
        "",
        f"- 明细结果：`{output_path.as_posix()}`",
        "",
        "## 计算口径",
        "",
        "- 输入价格：`data/etf_momentum_daily_eastmoney_qfq.csv`。",
        "- 价格口径：`adjust=qfq`，前复权收盘价 `close`。",
        "- 收益率公式：`return_n_months = current_close / lookback_close - 1`。",
        "- 回看日期：从当前交易日向前推 N 个自然月；若目标日期不是交易日，取该 ETF 在目标日期之前最近一个可用交易日。",
        "- 输出形态：长表；一行代表某 ETF 在某交易日、某 N 月窗口下的过去收益率。",
        "",
        "## 本次参数",
        "",
        f"- N 月窗口：{', '.join(map(str, months_list))}",
        f"- 最新日期：{latest_date.date()}",
        f"- 结果行数：{len(result)}",
        "",
        "## 最新日期截面的动量收益率",
        "",
        "| N个月 | 分层 | 代码 | 名称 | 主题 | 当前收盘 | 回看日期 | 回看收盘 | 过去N月收益率 |",
        "|---:|---|---|---|---|---:|---|---:|---:|",
    ]
    for row in latest.itertuples(index=False):
        lines.append(
            f"| {row.months} | {row.bucket} | {row.symbol} | {row.name} | {row.theme} | "
            f"{row.current_close:.4f} | {pd.Timestamp(row.lookback_actual_date).date()} | "
            f"{float(row.lookback_close):.4f} | {pct(row.return_n_months)} |"
        )

    lines.extend([
        "",
        "## 有效样本覆盖",
        "",
        "| 代码 | 名称 | 分层 | 主题 | N个月 | 总行数 | 有效行数 | 起始 | 结束 |",
        "|---|---|---|---|---:|---:|---:|---|---|",
    ])
    for row in coverage.sort_values(["bucket", "symbol", "months"]).itertuples(index=False):
        lines.append(
            f"| {row.symbol} | {row.name} | {row.bucket} | {row.theme} | {row.months} | "
            f"{row.rows} | {int(row.valid_rows)} | {pd.Timestamp(row.start).date()} | {pd.Timestamp(row.end).date()} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute individual ETF trailing N-month returns from qfq close prices.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--months", default="1,3,6,12,24,36,48,60,72", help="Comma-separated month windows, e.g. 1,3,6,12,24,36,48,60,72")
    args = parser.parse_args()

    months_list = parse_months(args.months)
    df = pd.read_csv(args.input, parse_dates=["date"], dtype={"symbol": "string"})
    required = {"date", "symbol", "name", "bucket", "theme", "close", "adjust", "source"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if df.empty:
        raise ValueError("Input data is empty")
    bad_adjust = sorted(set(df["adjust"].dropna()) - {"qfq"})
    if bad_adjust:
        raise ValueError(f"Unexpected adjust values: {bad_adjust}")

    rows: list[dict] = []
    for _, symbol_df in df.sort_values(["symbol", "date"]).groupby("symbol", sort=True):
        rows.extend(compute_single_symbol_returns(symbol_df, months_list))

    result = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.output, index=False, encoding="utf-8-sig")
    args.report.write_text(make_report(result, months_list, args.output), encoding="utf-8")

    print(f"Saved: {args.output}")
    print(f"Saved: {args.report}")
    print(f"Rows: {len(result)}; ETFs: {result['symbol'].nunique()}; months: {months_list}")
    print(result.groupby(["months", "valid"]).size().to_string())


if __name__ == "__main__":
    main()
