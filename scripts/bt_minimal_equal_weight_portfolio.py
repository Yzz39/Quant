from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
OUTPUT_DIR = BASE / "outputs"
SCRIPT_DIR = BASE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from performance_metrics import performance_summary

LOOKBACK_DAYS = 42
TOP_N_LIST = [2, 3]
INIT_CASH = 100_000.0
COMMISSION_RATE = 0.0001
SLIPPAGE_RATE = 0.0001
TOTAL_ONE_WAY_COST_RATE = COMMISSION_RATE + SLIPPAGE_RATE

SUMMARY_PATH = OUTPUT_DIR / "bt_minimal_equal_weight_summary.csv"
REPORT_PATH = OUTPUT_DIR / "bt_minimal_equal_weight_report.md"


REQUIRED_COLUMNS = {"date", "symbol", "close", "name", "bucket", "theme"}


def rebalance_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    dates = pd.Series(index, index=index)
    return pd.DatetimeIndex(dates.groupby(index.to_period("M")).last().values)


def load_market_data(data_path: Path = DATA_PATH) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], list[str], list[str]]:
    df = pd.read_csv(data_path, dtype={"symbol": "string"}, parse_dates=["date"])
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["symbol"] = df["symbol"].astype("string").str.strip()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.sort_values(["symbol", "date"])

    duplicated = df.duplicated(["symbol", "date"]).sum()
    if duplicated:
        raise ValueError(f"Found duplicated symbol/date rows: {duplicated}")
    if df["close"].isna().any() or df["close"].le(0).any():
        raise ValueError("close must be non-missing and positive")

    allowed_buckets = {"sector", "defensive", "benchmark"}
    unknown_buckets = sorted(set(df["bucket"].dropna()) - allowed_buckets)
    if unknown_buckets:
        raise ValueError(f"Unknown bucket values: {unknown_buckets}")

    meta = (
        df.groupby("symbol", as_index=False)
        .agg(name=("name", "last"), bucket=("bucket", "last"), theme=("theme", "last"))
        .sort_values("symbol")
    )
    close = df.pivot(index="date", columns="symbol", values="close").sort_index().sort_index(axis=1)
    sector_symbols = meta.loc[meta["bucket"].eq("sector"), "symbol"].tolist()
    defensive_symbols = meta.loc[meta["bucket"].eq("defensive"), "symbol"].tolist()
    benchmark_symbols = meta.loc[meta["bucket"].eq("benchmark"), "symbol"].tolist()

    if len(sector_symbols) < max(TOP_N_LIST):
        raise ValueError("Not enough sector ETFs for TopN rotation")
    if not defensive_symbols:
        raise ValueError("At least one defensive ETF is required")
    if not benchmark_symbols:
        raise ValueError("At least one benchmark ETF is required")

    return df, meta, close, sector_symbols, defensive_symbols, benchmark_symbols


def build_month_end_decisions(
    close: pd.DataFrame,
    meta: pd.DataFrame,
    sector_symbols: list[str],
    defensive_symbols: list[str],
    top_n: int,
    lookback_days: int = LOOKBACK_DAYS,
) -> pd.DataFrame:
    meta_by_symbol = meta.set_index("symbol")
    momentum = close / close.shift(lookback_days) - 1.0
    decisions: list[dict[str, object]] = []

    for signal_date in rebalance_dates(close.index):
        row = momentum.loc[signal_date]
        sector_momentum = row[sector_symbols].dropna().sort_values(ascending=False)
        defensive_momentum = row[defensive_symbols].dropna().sort_values(ascending=False)
        positive_sector = sector_momentum[sector_momentum > 0]

        selected_symbols: list[str] = []
        selected_bucket = "cash"
        reason = "行业和防守资产均无正动量，空仓"

        if not positive_sector.empty:
            selected_symbols = positive_sector.head(top_n).index.tolist()
            selected_bucket = "sector"
            reason = f"选择正动量行业/主题 ETF Top{top_n}，等权持有"
        elif not defensive_momentum.empty and defensive_momentum.iloc[0] > 0:
            selected_symbols = [defensive_momentum.index[0]]
            selected_bucket = "defensive"
            reason = "行业/主题 ETF 无正动量，切换到正动量防守资产"

        selected_names = [str(meta_by_symbol.loc[symbol, "name"]) for symbol in selected_symbols] or ["空仓"]
        selected_themes = [str(meta_by_symbol.loc[symbol, "theme"]) for symbol in selected_symbols] or ["现金"]
        selected_momentums = [float(row[symbol]) for symbol in selected_symbols]

        decisions.append(
            {
                "signal_date": signal_date,
                "top_n": top_n,
                "selected_symbols": "|".join(selected_symbols) if selected_symbols else "CASH",
                "selected_names": "|".join(selected_names),
                "selected_bucket": selected_bucket,
                "selected_themes": "|".join(selected_themes),
                "selected_count": len(selected_symbols),
                "target_weight_each": 1.0 / len(selected_symbols) if selected_symbols else 0.0,
                "selected_momentums": "|".join(f"{value:.8f}" for value in selected_momentums),
                "reason": reason,
            }
        )

    return pd.DataFrame(decisions)


def build_target_weights(close: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    target_weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    decision_by_date = decisions.set_index("signal_date")
    current_symbols: list[str] = []
    next_symbols: list[str] | None = None

    for date in close.index:
        if next_symbols is not None:
            current_symbols = next_symbols
            next_symbols = None

        if current_symbols:
            weight = 1.0 / len(current_symbols)
            target_weights.loc[date, current_symbols] = weight

        if date in decision_by_date.index:
            selected = str(decision_by_date.loc[date, "selected_symbols"])
            next_symbols = [] if selected == "CASH" else selected.split("|")

    return target_weights


def run_minimal_backtest(
    close: pd.DataFrame,
    target_weights: pd.DataFrame,
    init_cash: float = INIT_CASH,
    one_way_cost_rate: float = TOTAL_ONE_WAY_COST_RATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    returns = close.pct_change(fill_method=None).fillna(0.0)
    weights = target_weights.reindex(index=returns.index, columns=returns.columns).fillna(0.0)
    previous_weights = weights.shift(1).fillna(0.0)

    gross_return = (previous_weights * returns).sum(axis=1)
    buys = (weights - previous_weights).clip(lower=0).sum(axis=1)
    sells = (previous_weights - weights).clip(lower=0).sum(axis=1)
    one_way_turnover = pd.concat([buys, sells], axis=1).max(axis=1)
    two_way_traded = buys + sells
    cost = one_way_turnover * one_way_cost_rate
    net_return = gross_return - cost
    nav = (1.0 + net_return).cumprod()

    daily = pd.DataFrame(
        {
            "date": returns.index,
            "portfolio_value": init_cash * nav.values,
            "nav": nav.values,
            "gross_return": gross_return.values,
            "cost": cost.values,
            "daily_return": net_return.values,
            "one_way_turnover": one_way_turnover.values,
            "two_way_traded": two_way_traded.values,
        }
    )

    trades = (
        pd.DataFrame(
            {
                "date": returns.index,
                "buy_turnover": buys.values,
                "sell_turnover": sells.values,
                "one_way_turnover": one_way_turnover.values,
                "two_way_traded": two_way_traded.values,
                "estimated_cost": cost.values,
            }
        )
        .loc[lambda x: x["two_way_traded"].gt(1e-12)]
        .reset_index(drop=True)
    )
    return daily, trades


def benchmark_daily(close: pd.DataFrame, benchmark_symbols: list[str]) -> pd.DataFrame:
    benchmark_symbol = "510300" if "510300" in benchmark_symbols else benchmark_symbols[0]
    benchmark_return = close[benchmark_symbol].pct_change(fill_method=None).fillna(0.0)
    benchmark_nav = (1.0 + benchmark_return).cumprod()
    return pd.DataFrame(
        {
            "date": close.index,
            "benchmark_symbol": benchmark_symbol,
            "portfolio_value": INIT_CASH * benchmark_nav.values,
            "nav": benchmark_nav.values,
            "daily_return": benchmark_return.values,
        }
    )


def summarize_strategy(name: str, daily: pd.DataFrame, top_n: int, trades: pd.DataFrame) -> dict[str, object]:
    metrics = performance_summary(daily["daily_return"], equity=daily["nav"], periods_per_year=252)
    years = len(daily) / 252
    total_turnover = float(daily["one_way_turnover"].sum()) if "one_way_turnover" in daily else 0.0
    total_cost = float(daily["cost"].sum()) if "cost" in daily else 0.0
    return {
        "name": name,
        "top_n": top_n,
        "lookback_days": LOOKBACK_DAYS if top_n else 0,
        "rebalance_frequency": "monthly" if top_n else "buy_hold",
        "init_cash": INIT_CASH,
        "one_way_cost_rate": TOTAL_ONE_WAY_COST_RATE if top_n else 0.0,
        "total_return": metrics["total_return"],
        "annualized_return": metrics["cagr"],
        "annualized_volatility": metrics["annual_vol"],
        "max_drawdown": metrics["max_drawdown"],
        "sharpe_like_no_rf": metrics["sharpe_ratio"],
        "final_value": float(daily["portfolio_value"].iloc[-1]),
        "trade_day_count": int(len(trades)),
        "total_one_way_turnover": total_turnover,
        "annual_one_way_turnover": float(total_turnover / years),
        "total_cost_drag": total_cost,
        "cash_target_days": int(daily.get("cash_target", pd.Series(dtype=bool)).sum()) if "cash_target" in daily else 0,
    }


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    def fmt(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, float):
            return f"{value:.6f}"
        return str(value)

    header = "| " + " | ".join(df.columns.astype(str)) + " |"
    separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows = ["| " + " | ".join(fmt(value) for value in row) + " |" for row in df.itertuples(index=False, name=None)]
    return "\n".join([header, separator, *rows])


def write_report(summary: pd.DataFrame, latest_decisions: list[pd.Series]) -> None:
    lines = [
        "# bt 组合回测最小版本报告",
        "",
        "## 定位",
        "",
        "这是一个不依赖 vectorbt 的最小 pandas 组合回测，用来理解组合权重、再平衡、成本和净值的基本关系。",
        "",
        "## 规则",
        "",
        f"- 数据：`{DATA_PATH.as_posix()}`。",
        f"- 动量：`close / close.shift({LOOKBACK_DAYS}) - 1`。",
        "- 调仓：每月最后一个交易日收盘后生成信号，下一交易日开始持有目标权重。",
        "- 组合：行业/主题 ETF 正动量 Top2/Top3 等权；无正动量行业 ETF 时切防守资产；否则空仓。",
        f"- 成本：单边佣金 `{COMMISSION_RATE:.4%}` + 滑点 `{SLIPPAGE_RATE:.4%}`，按单边换手扣除。",
        "",
        "## 汇总指标",
        "",
        dataframe_to_markdown(summary),
        "",
        "## 最新信号",
        "",
    ]
    for decision in latest_decisions:
        lines.extend(
            [
                f"- Top{int(decision['top_n'])}：{pd.to_datetime(decision['signal_date']).date()}，`{decision['selected_symbols']}`，{decision['selected_names']}，原因：{decision['reason']}",
            ]
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    _, meta, close, sector_symbols, defensive_symbols, benchmark_symbols = load_market_data()
    summary_rows: list[dict[str, object]] = []
    latest_decisions: list[pd.Series] = []

    for top_n in TOP_N_LIST:
        prefix = f"bt_minimal_top{top_n}_equal_weight"
        decisions = build_month_end_decisions(close, meta, sector_symbols, defensive_symbols, top_n)
        target_weights = build_target_weights(close, decisions)
        daily, trades = run_minimal_backtest(close, target_weights)
        daily["cash_target"] = target_weights.sum(axis=1).eq(0).values

        decisions.to_csv(OUTPUT_DIR / f"{prefix}_decisions.csv", index=False, encoding="utf-8-sig")
        target_weights.reset_index(names="date").to_csv(OUTPUT_DIR / f"{prefix}_target_weights.csv", index=False, encoding="utf-8-sig")
        daily.to_csv(OUTPUT_DIR / f"{prefix}_daily_value.csv", index=False, encoding="utf-8-sig")
        trades.to_csv(OUTPUT_DIR / f"{prefix}_trades.csv", index=False, encoding="utf-8-sig")

        summary_rows.append(summarize_strategy(prefix, daily, top_n, trades))
        latest_decisions.append(decisions.iloc[-1])

    bench = benchmark_daily(close, benchmark_symbols)
    empty_trades = pd.DataFrame(columns=["date"])
    summary_rows.append(summarize_strategy(f"buy_hold_{bench['benchmark_symbol'].iloc[0]}", bench, 0, empty_trades))

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    write_report(summary, latest_decisions)

    print(f"Saved summary: {SUMMARY_PATH}")
    print(f"Saved report: {REPORT_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
