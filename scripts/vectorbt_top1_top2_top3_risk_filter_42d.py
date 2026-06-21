from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
OUTPUT_DIR = BASE / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

LOOKBACK_DAYS = 42
REBALANCE_FREQUENCY = "monthly"
TOP_N_LIST = [1, 2, 3]
INIT_CASH = 100_000.0
FEE_RATE = 0.0001
SLIPPAGE = 0.0001

SUMMARY_METRICS_PATH = OUTPUT_DIR / "etf_top1_top2_top3_risk_filter_42d_vectorbt_metrics.csv"
COMPARISON_PATH = OUTPUT_DIR / "etf_top1_top2_top3_risk_filter_42d_comparison.csv"
REPORT_PATH = OUTPUT_DIR / "etf_top1_top2_top3_risk_filter_42d_report.md"


def output_paths(top_n: int) -> dict[str, Path]:
    prefix = f"etf_top{top_n}_risk_filter_42d_vectorbt"
    return {
        "daily": OUTPUT_DIR / f"{prefix}_daily_value.csv",
        "weights": OUTPUT_DIR / f"{prefix}_target_weights.csv",
        "decisions": OUTPUT_DIR / f"{prefix}_decisions.csv",
        "orders": OUTPUT_DIR / f"{prefix}_orders.csv",
        "metrics": OUTPUT_DIR / f"{prefix}_metrics.csv",
    }


def rebalance_dates_for_frequency(index: pd.DatetimeIndex, frequency: str) -> pd.DatetimeIndex:
    dates = pd.Series(index, index=index)
    if frequency == "weekly":
        return pd.DatetimeIndex(dates.groupby(index.to_period("W-FRI")).last().values)
    if frequency == "biweekly":
        weekly = pd.DatetimeIndex(dates.groupby(index.to_period("W-FRI")).last().values)
        return weekly[1::2]
    if frequency == "monthly":
        return pd.DatetimeIndex(dates.groupby(index.to_period("M")).last().values)
    if frequency == "quarterly":
        return pd.DatetimeIndex(dates.groupby(index.to_period("Q")).last().values)
    raise ValueError(f"Unknown frequency: {frequency}")


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.cummax()
    return float((nav / peak - 1.0).min())


def annualized_return(nav: pd.Series, periods_per_year: int = 252) -> float:
    if len(nav) < 2:
        return np.nan
    total = nav.iloc[-1] / nav.iloc[0] - 1.0
    years = len(nav) / periods_per_year
    return float((1.0 + total) ** (1.0 / years) - 1.0)


def annualized_volatility(ret: pd.Series, periods_per_year: int = 252) -> float:
    return float(ret.std() * np.sqrt(periods_per_year))


def sharpe_like(ret: pd.Series, periods_per_year: int = 252) -> float:
    vol = annualized_volatility(ret, periods_per_year)
    if vol == 0 or pd.isna(vol):
        return np.nan
    return float(ret.mean() * periods_per_year / vol)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, list[str], list[str], list[str]]:
    df = pd.read_csv(DATA_PATH, dtype={"symbol": "string"}, parse_dates=["date"])
    df["symbol"] = df["symbol"].astype("string").str.strip()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.sort_values(["symbol", "date"])

    meta = (
        df.groupby("symbol")
        .agg(
            name=("name", "last"),
            bucket=("bucket", "last"),
            theme=("theme", "last"),
            first_date=("date", "min"),
            last_date=("date", "max"),
            rows=("date", "size"),
        )
        .reset_index()
    )
    close = df.pivot(index="date", columns="symbol", values="close").sort_index().sort_index(axis=1)
    sector_symbols = meta.loc[meta["bucket"].eq("sector"), "symbol"].tolist()
    defensive_symbols = meta.loc[meta["bucket"].eq("defensive"), "symbol"].tolist()
    benchmark_symbols = meta.loc[meta["bucket"].eq("benchmark"), "symbol"].tolist()
    return meta, close, sector_symbols, defensive_symbols, benchmark_symbols


def build_decisions_and_weights(
    close: pd.DataFrame,
    meta: pd.DataFrame,
    sector_symbols: list[str],
    defensive_symbols: list[str],
    top_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    meta_by_symbol = meta.set_index("symbol")
    signal_dates = rebalance_dates_for_frequency(close.index, REBALANCE_FREQUENCY)
    momentum = close / close.shift(LOOKBACK_DAYS) - 1.0
    decisions = []

    for signal_date in signal_dates:
        row = momentum.loc[signal_date]
        sector_mom = row[sector_symbols].dropna().sort_values(ascending=False)
        defensive_mom = row[defensive_symbols].dropna().sort_values(ascending=False)
        positive_sector_mom = sector_mom[sector_mom > 0]

        selected_symbols: list[str] = []
        selected_bucket = "cash"
        reason = "行业/主题 ETF 与防守资产均无正动量，空仓"
        best_sector_symbol = None
        best_sector_momentum = np.nan
        best_defensive_symbol = None
        best_defensive_momentum = np.nan
        risk_state = "cash"

        if not sector_mom.empty:
            best_sector_symbol = sector_mom.index[0]
            best_sector_momentum = float(sector_mom.iloc[0])
        if not defensive_mom.empty:
            best_defensive_symbol = defensive_mom.index[0]
            best_defensive_momentum = float(defensive_mom.iloc[0])

        if not positive_sector_mom.empty:
            selected_symbols = positive_sector_mom.head(top_n).index.tolist()
            selected_bucket = "sector"
            risk_state = "risk_on"
            reason = f"风险过滤通过：行业/主题 ETF 存在正动量，选择 Top{top_n} 正动量标的等权持有"
        elif pd.notna(best_defensive_momentum) and best_defensive_momentum > 0:
            selected_symbols = [best_defensive_symbol]
            selected_bucket = "defensive"
            risk_state = "defensive"
            reason = f"风险过滤触发：行业/主题 ETF 无正动量，切到正动量防守资产"

        if selected_symbols:
            selected_names = [str(meta_by_symbol.loc[symbol, "name"]) for symbol in selected_symbols]
            selected_themes = [str(meta_by_symbol.loc[symbol, "theme"]) for symbol in selected_symbols]
            selected_momentums = [float(row[symbol]) for symbol in selected_symbols]
            selected_weight = 1.0 / len(selected_symbols)
        else:
            selected_names = ["空仓"]
            selected_themes = ["现金"]
            selected_momentums = []
            selected_weight = 0.0

        top_sector_symbols = sector_mom.head(top_n).index.tolist()
        top_sector_momentums = [float(value) for value in sector_mom.head(top_n).values]

        decisions.append(
            {
                "signal_date": signal_date,
                "top_n": top_n,
                "risk_state": risk_state,
                "selected_symbols": "|".join(selected_symbols) if selected_symbols else "CASH",
                "selected_names": "|".join(selected_names),
                "selected_bucket": selected_bucket,
                "selected_themes": "|".join(selected_themes),
                "selected_count": len(selected_symbols),
                "target_weight_each": selected_weight,
                "selected_momentums": "|".join(f"{value:.8f}" for value in selected_momentums),
                "top_sector_symbols": "|".join(top_sector_symbols),
                "top_sector_momentums": "|".join(f"{value:.8f}" for value in top_sector_momentums),
                "best_sector_symbol": best_sector_symbol,
                "best_sector_momentum": best_sector_momentum,
                "best_defensive_symbol": best_defensive_symbol,
                "best_defensive_momentum": best_defensive_momentum,
                "reason": reason,
            }
        )

    decisions = pd.DataFrame(decisions)
    target_weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    decision_by_date = decisions.set_index("signal_date")
    current_symbols: list[str] = []

    for date in close.index:
        if current_symbols:
            weight = 1.0 / len(current_symbols)
            for symbol in current_symbols:
                if symbol in target_weights.columns:
                    target_weights.loc[date, symbol] = weight
        if date in decision_by_date.index:
            selected = str(decision_by_date.loc[date, "selected_symbols"])
            current_symbols = [] if selected == "CASH" else selected.split("|")

    return decisions, target_weights


def run_vectorbt(close: pd.DataFrame, target_weights: pd.DataFrame) -> vbt.Portfolio:
    return vbt.Portfolio.from_orders(
        close=close,
        size=target_weights,
        size_type="targetpercent",
        group_by=True,
        cash_sharing=True,
        init_cash=INIT_CASH,
        fees=FEE_RATE,
        slippage=SLIPPAGE,
        freq="1D",
    )


def build_outputs(
    pf: vbt.Portfolio,
    close: pd.DataFrame,
    target_weights: pd.DataFrame,
    decisions: pd.DataFrame,
    benchmark_symbols: list[str],
    top_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    paths = output_paths(top_n)
    value = pf.value()
    if isinstance(value, pd.DataFrame):
        value = value.iloc[:, 0]
    value = value.rename("portfolio_value")
    daily_ret = value.pct_change().fillna(0.0)
    daily = pd.DataFrame(
        {
            "date": value.index,
            "portfolio_value": value.values,
            "nav": (value / INIT_CASH).values,
            "daily_return": daily_ret.values,
        }
    )

    orders = pf.orders.records_readable.copy()
    orders.to_csv(paths["orders"], index=False, encoding="utf-8-sig")

    benchmark_symbol = "510300" if "510300" in close.columns else benchmark_symbols[0]
    benchmark_ret = close[benchmark_symbol].pct_change(fill_method=None).fillna(0.0)
    benchmark_nav = (1.0 + benchmark_ret).cumprod()
    years = len(value) / 252
    order_count = len(orders)
    total_fees = float(orders["Fees"].sum()) if "Fees" in orders.columns else np.nan
    total_order_value = float((orders["Size"] * orders["Price"]).abs().sum()) if {"Size", "Price"}.issubset(orders.columns) else np.nan
    annual_traded_value_ratio = total_order_value / INIT_CASH / years if pd.notna(total_order_value) else np.nan
    active_counts = target_weights.gt(0).sum(axis=1)

    metrics = pd.DataFrame(
        [
            {
                "name": f"vectorbt_top{top_n}_risk_filter_42d",
                "top_n": top_n,
                "lookback_days": LOOKBACK_DAYS,
                "rebalance_frequency": REBALANCE_FREQUENCY,
                "init_cash": INIT_CASH,
                "fee_rate": FEE_RATE,
                "slippage": SLIPPAGE,
                "total_return": value.iloc[-1] / value.iloc[0] - 1.0,
                "annualized_return": annualized_return(value / INIT_CASH),
                "annualized_volatility": annualized_volatility(daily_ret),
                "max_drawdown": max_drawdown(value / INIT_CASH),
                "sharpe_like_no_rf": sharpe_like(daily_ret),
                "final_value": float(value.iloc[-1]),
                "order_count": order_count,
                "total_fees": total_fees,
                "total_order_value": total_order_value,
                "annual_traded_value_ratio": annual_traded_value_ratio,
                "cash_target_days": int(active_counts.eq(0).sum()),
                "single_asset_target_days": int(active_counts.eq(1).sum()),
                "multi_asset_target_days": int(active_counts.gt(1).sum()),
                "risk_on_signals": int(decisions["risk_state"].eq("risk_on").sum()),
                "defensive_signals": int(decisions["risk_state"].eq("defensive").sum()),
                "cash_signals": int(decisions["risk_state"].eq("cash").sum()),
            },
            {
                "name": f"buy_hold_{benchmark_symbol}",
                "top_n": 0,
                "lookback_days": 0,
                "rebalance_frequency": "buy_hold",
                "init_cash": INIT_CASH,
                "fee_rate": 0.0,
                "slippage": 0.0,
                "total_return": benchmark_nav.iloc[-1] / benchmark_nav.iloc[0] - 1.0,
                "annualized_return": annualized_return(benchmark_nav),
                "annualized_volatility": annualized_volatility(benchmark_ret),
                "max_drawdown": max_drawdown(benchmark_nav),
                "sharpe_like_no_rf": sharpe_like(benchmark_ret),
                "final_value": float(INIT_CASH * benchmark_nav.iloc[-1]),
                "order_count": 0,
                "total_fees": 0.0,
                "total_order_value": 0.0,
                "annual_traded_value_ratio": 0.0,
                "cash_target_days": 0,
                "single_asset_target_days": len(close),
                "multi_asset_target_days": 0,
                "risk_on_signals": 0,
                "defensive_signals": 0,
                "cash_signals": 0,
            },
        ]
    )

    daily.to_csv(paths["daily"], index=False, encoding="utf-8-sig")
    target_weights.reset_index(names="date").to_csv(paths["weights"], index=False, encoding="utf-8-sig")
    decisions.to_csv(paths["decisions"], index=False, encoding="utf-8-sig")
    metrics.to_csv(paths["metrics"], index=False, encoding="utf-8-sig")
    return daily, orders, metrics


def format_markdown_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    header = "| " + " | ".join(df.columns.astype(str)) + " |"
    separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows = [
        "| " + " | ".join(format_markdown_value(value) for value in row) + " |"
        for row in df.itertuples(index=False, name=None)
    ]
    return "\n".join([header, separator, *rows])


def build_comparison(summary_metrics: pd.DataFrame) -> pd.DataFrame:
    baseline_rows = []
    top1_path = OUTPUT_DIR / "etf_top1_rotation_vectorbt_metrics.csv"
    topn_path = OUTPUT_DIR / "etf_topn_rotation_vectorbt_metrics.csv"

    if top1_path.exists():
        top1 = pd.read_csv(top1_path)
        baseline_rows.append(top1[top1["name"].eq("vectorbt_top1_rotation")].assign(version="原 Top1 42日"))
    if topn_path.exists():
        topn = pd.read_csv(topn_path)
        baseline_rows.append(topn[topn["name"].eq("vectorbt_top2_equal_weight_rotation")].assign(version="原 Top2 42日"))
        baseline_rows.append(topn[topn["name"].eq("vectorbt_top3_equal_weight_rotation")].assign(version="原 Top3 42日"))

    risk_rows = []
    for top_n in TOP_N_LIST:
        risk_row = summary_metrics[summary_metrics["name"].eq(f"vectorbt_top{top_n}_risk_filter_42d")].copy()
        risk_row["version"] = f"风险过滤 Top{top_n} 42日"
        risk_rows.append(risk_row)

    comparison = pd.concat(baseline_rows + risk_rows, ignore_index=True, sort=False)
    columns = [
        "version",
        "name",
        "top_n",
        "lookback_days",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
        "sharpe_like_no_rf",
        "final_value",
        "order_count",
        "total_fees",
        "annual_traded_value_ratio",
        "cash_target_days",
        "single_asset_target_days",
        "multi_asset_target_days",
        "risk_on_signals",
        "defensive_signals",
        "cash_signals",
    ]
    return comparison[[column for column in columns if column in comparison.columns]]


def write_report(summary_metrics: pd.DataFrame, comparison: pd.DataFrame, all_decisions: dict[int, pd.DataFrame]) -> None:
    report_columns = [
        "version",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
        "sharpe_like_no_rf",
        "order_count",
        "cash_target_days",
        "defensive_signals",
        "cash_signals",
    ]
    report_table = comparison[[column for column in report_columns if column in comparison.columns]].copy()

    lines = [
        "# Top1/Top2/Top3 42日动量风险过滤 vectorbt 对比报告",
        "",
        "## 规则",
        "",
        f"- 动量窗口：`{LOOKBACK_DAYS}` 个交易日。",
        f"- 调仓频率：`{REBALANCE_FREQUENCY}`，调仓日收盘后生成信号，下一交易日目标权重生效。",
        "- 风险过滤：若行业/主题 ETF 存在正动量，则选择 TopN 正动量标的等权持有。",
        "- 若行业/主题 ETF 均无正动量，则切换到正动量防守资产；若防守资产也无正动量，则空仓。",
        f"- vectorbt 成本：佣金 `{FEE_RATE:.4%}`，滑点 `{SLIPPAGE:.4%}`。",
        "",
        "## 同窗口对比",
        "",
        dataframe_to_markdown(report_table),
        "",
        "## 输出文件",
        "",
        f"- 风险过滤汇总指标：`{SUMMARY_METRICS_PATH.as_posix()}`",
        f"- 与原始 Top1/Top2/Top3 对比：`{COMPARISON_PATH.as_posix()}`",
    ]

    for top_n in TOP_N_LIST:
        paths = output_paths(top_n)
        latest = all_decisions[top_n].iloc[-1]
        strategy = summary_metrics.loc[summary_metrics["name"].eq(f"vectorbt_top{top_n}_risk_filter_42d")].iloc[0]
        lines.extend(
            [
                "",
                f"## 风险过滤 Top{top_n} 最新信号",
                "",
                f"- 信号日：{pd.to_datetime(latest['signal_date']).date()}",
                f"- 风险状态：`{latest['risk_state']}`",
                f"- 选择：`{latest['selected_symbols']}` {latest['selected_names']}",
                f"- 单只目标权重：{latest['target_weight_each']:.2%}",
                f"- 年化收益：{strategy['annualized_return']:.2%}",
                f"- 最大回撤：{strategy['max_drawdown']:.2%}",
                f"- 每日净值：`{paths['daily'].as_posix()}`",
                f"- 目标权重：`{paths['weights'].as_posix()}`",
                f"- 调仓决策：`{paths['decisions'].as_posix()}`",
                f"- 订单明细：`{paths['orders'].as_posix()}`",
                f"- 指标：`{paths['metrics'].as_posix()}`",
            ]
        )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    meta, close, sector_symbols, defensive_symbols, benchmark_symbols = load_data()
    metrics_list = []
    all_decisions = {}
    all_orders = {}

    for top_n in TOP_N_LIST:
        decisions, target_weights = build_decisions_and_weights(close, meta, sector_symbols, defensive_symbols, top_n)
        pf = run_vectorbt(close, target_weights)
        _, orders, metrics = build_outputs(pf, close, target_weights, decisions, benchmark_symbols, top_n)
        all_decisions[top_n] = decisions
        all_orders[top_n] = orders
        metrics_list.append(metrics.iloc[[0]])

    benchmark_metrics = metrics.iloc[[1]]
    summary_metrics = pd.concat(metrics_list + [benchmark_metrics], ignore_index=True)
    summary_metrics.to_csv(SUMMARY_METRICS_PATH, index=False, encoding="utf-8-sig")

    comparison = build_comparison(summary_metrics)
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    write_report(summary_metrics, comparison, all_decisions)

    print(f"vectorbt version: {vbt.__version__}")
    for top_n in TOP_N_LIST:
        paths = output_paths(top_n)
        print(f"Saved Top{top_n} risk-filter daily value: {paths['daily']}")
        print(f"Saved Top{top_n} risk-filter target weights: {paths['weights']}")
        print(f"Saved Top{top_n} risk-filter decisions: {paths['decisions']}")
        print(f"Saved Top{top_n} risk-filter orders: {paths['orders']}")
        print(f"Saved Top{top_n} risk-filter metrics: {paths['metrics']}")
    print(f"Saved summary metrics: {SUMMARY_METRICS_PATH}")
    print(f"Saved comparison: {COMPARISON_PATH}")
    print(f"Saved report: {REPORT_PATH}")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
