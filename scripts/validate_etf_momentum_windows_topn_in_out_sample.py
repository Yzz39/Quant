from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
OUTPUT_DIR = BASE / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

WINDOWS = [
    ("1m", 21),
    ("2m", 42),
    ("3m", 63),
    ("6m", 126),
    ("9m", 189),
    ("12m", 252),
]
TOP_N_LIST = [1, 2, 3]
SEGMENTS = [
    ("full_sample", "全样本", "2015-01-05", "2026-06-18"),
    ("in_sample", "样本内", "2015-01-05", "2021-12-31"),
    ("out_of_sample", "样本外", "2022-01-01", "2026-06-18"),
    ("full_universe", "完整ETF池期", "2021-03-02", "2026-06-18"),
]

REBALANCE_FREQUENCY = "monthly"
INIT_CASH = 100_000.0
FEE_RATE = 0.0001
SLIPPAGE = 0.0001

DAILY_PATH = OUTPUT_DIR / "etf_momentum_windows_topn_vectorbt_daily.csv"
DECISIONS_PATH = OUTPUT_DIR / "etf_momentum_windows_topn_vectorbt_decisions.csv"
FULL_METRICS_PATH = OUTPUT_DIR / "etf_momentum_windows_topn_vectorbt_full_metrics.csv"
SEGMENT_METRICS_PATH = OUTPUT_DIR / "etf_momentum_windows_topn_in_out_sample_metrics.csv"
STABILITY_SUMMARY_PATH = OUTPUT_DIR / "etf_momentum_windows_topn_in_out_sample_summary.csv"
OOS_RANKING_PATH = OUTPUT_DIR / "etf_momentum_windows_topn_oos_ranking.csv"
REPORT_PATH = OUTPUT_DIR / "etf_momentum_windows_topn_in_out_sample_report.md"


def rebalance_dates_for_frequency(index: pd.DatetimeIndex, frequency: str) -> pd.DatetimeIndex:
    dates = pd.Series(index, index=index)
    if frequency == "monthly":
        return pd.DatetimeIndex(dates.groupby(index.to_period("M")).last().values)
    raise ValueError(f"Unknown frequency: {frequency}")


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.cummax()
    return float((nav / peak - 1.0).min())


def annualized_return(nav: pd.Series, periods_per_year: int = 252) -> float:
    if len(nav) < 2:
        return np.nan
    total = nav.iloc[-1] / nav.iloc[0] - 1.0
    years = len(nav) / periods_per_year
    if years <= 0 or total <= -1:
        return np.nan
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
    window_label: str,
    lookback_days: int,
    top_n: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    meta_by_symbol = meta.set_index("symbol")
    signal_dates = rebalance_dates_for_frequency(close.index, REBALANCE_FREQUENCY)
    momentum = close / close.shift(lookback_days) - 1.0
    decisions = []

    for signal_date in signal_dates:
        row = momentum.loc[signal_date]
        sector_mom = row[sector_symbols].dropna().sort_values(ascending=False)
        defensive_mom = row[defensive_symbols].dropna().sort_values(ascending=False)
        positive_sector_mom = sector_mom[sector_mom > 0]

        selected_symbols: list[str] = []
        selected_bucket = "cash"
        risk_state = "cash"
        reason = "行业/主题 ETF 与防守资产均无正动量，空仓"
        best_sector_symbol = None
        best_sector_momentum = np.nan
        best_defensive_symbol = None
        best_defensive_momentum = np.nan

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
            reason = f"{window_label} 动量窗口：选择 Top{top_n} 正动量行业/主题 ETF 等权持有"
        elif pd.notna(best_defensive_momentum) and best_defensive_momentum > 0:
            selected_symbols = [best_defensive_symbol]
            selected_bucket = "defensive"
            risk_state = "defensive"
            reason = f"{window_label} 动量窗口：行业/主题 ETF 无正动量，切到正动量防守资产"

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
                "strategy_key": f"top{top_n}_{window_label}",
                "strategy_name": f"Top{top_n} {window_label}",
                "window_label": window_label,
                "lookback_days": lookback_days,
                "top_n": top_n,
                "signal_date": signal_date,
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


def portfolio_value_series(pf: vbt.Portfolio) -> pd.Series:
    value = pf.value()
    if isinstance(value, pd.DataFrame):
        value = value.iloc[:, 0]
    return value.rename("portfolio_value")


def calc_metrics_from_nav(nav: pd.Series) -> dict[str, float]:
    ret = nav.pct_change().fillna(0.0)
    return {
        "total_return": float(nav.iloc[-1] / nav.iloc[0] - 1.0),
        "annualized_return": annualized_return(nav),
        "annualized_volatility": annualized_volatility(ret),
        "max_drawdown": max_drawdown(nav),
        "sharpe_like_no_rf": sharpe_like(ret),
    }


def calc_segment_metrics(daily: pd.DataFrame, segment_key: str, segment_name: str, start: str, end: str) -> dict[str, object]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    segment = daily[(daily["date"] >= start_ts) & (daily["date"] <= end_ts)].copy()
    if segment.empty:
        return {
            "segment_key": segment_key,
            "segment_name": segment_name,
            "segment_start": start,
            "segment_end": end,
            "actual_start": None,
            "actual_end": None,
            "trading_days": 0,
            "total_return": np.nan,
            "annualized_return": np.nan,
            "annualized_volatility": np.nan,
            "max_drawdown": np.nan,
            "sharpe_like_no_rf": np.nan,
        }
    nav = segment["nav"] / segment["nav"].iloc[0]
    metrics = calc_metrics_from_nav(nav)
    metrics.update(
        {
            "segment_key": segment_key,
            "segment_name": segment_name,
            "segment_start": start,
            "segment_end": end,
            "actual_start": segment["date"].iloc[0].date().isoformat(),
            "actual_end": segment["date"].iloc[-1].date().isoformat(),
            "trading_days": len(segment),
        }
    )
    return metrics


def classify_stability(annualized_decay: float, drawdown_change: float, sharpe_decay: float) -> str:
    if pd.isna(annualized_decay) or pd.isna(drawdown_change) or pd.isna(sharpe_decay):
        return "数据不足"
    if annualized_decay < -0.15 and (drawdown_change < -0.10 or sharpe_decay < -0.40):
        return "样本外明显退化"
    if annualized_decay < -0.08 or drawdown_change < -0.06 or sharpe_decay < -0.25:
        return "样本外有所退化"
    if annualized_decay > 0 and drawdown_change > -0.03:
        return "样本外保持较好"
    return "基本稳定"


def format_percent(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.2%}"


def format_float(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.2f}"


def dataframe_to_markdown(df: pd.DataFrame, percent_cols: set[str] | None = None, float_cols: set[str] | None = None) -> str:
    percent_cols = percent_cols or set()
    float_cols = float_cols or set()
    header = "| " + " | ".join(df.columns.astype(str)) + " |"
    separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows = []
    for row in df.itertuples(index=False, name=None):
        values = []
        for column, value in zip(df.columns, row):
            if column in percent_cols:
                values.append(format_percent(value))
            elif column in float_cols:
                values.append(format_float(value))
            elif pd.isna(value):
                values.append("")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join([header, separator, *rows])


def build_summary(segment_metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in segment_metrics.groupby(["strategy_key", "strategy_name", "window_label", "lookback_days", "top_n"], sort=False):
        strategy_key, strategy_name, window_label, lookback_days, top_n = keys
        indexed = group.set_index("segment_key")
        full = indexed.loc["full_sample"]
        ins = indexed.loc["in_sample"]
        oos = indexed.loc["out_of_sample"]
        full_universe = indexed.loc["full_universe"]
        annualized_decay = oos["annualized_return"] - ins["annualized_return"]
        drawdown_change = oos["max_drawdown"] - ins["max_drawdown"]
        sharpe_decay = oos["sharpe_like_no_rf"] - ins["sharpe_like_no_rf"]
        rows.append(
            {
                "strategy_key": strategy_key,
                "strategy_name": strategy_name,
                "window_label": window_label,
                "lookback_days": lookback_days,
                "top_n": top_n,
                "full_annualized_return": full["annualized_return"],
                "full_max_drawdown": full["max_drawdown"],
                "is_annualized_return": ins["annualized_return"],
                "is_max_drawdown": ins["max_drawdown"],
                "is_sharpe_like_no_rf": ins["sharpe_like_no_rf"],
                "oos_annualized_return": oos["annualized_return"],
                "oos_max_drawdown": oos["max_drawdown"],
                "oos_sharpe_like_no_rf": oos["sharpe_like_no_rf"],
                "full_universe_annualized_return": full_universe["annualized_return"],
                "full_universe_max_drawdown": full_universe["max_drawdown"],
                "annualized_return_oos_minus_is": annualized_decay,
                "max_drawdown_oos_minus_is": drawdown_change,
                "sharpe_oos_minus_is": sharpe_decay,
                "stability_flag": classify_stability(annualized_decay, drawdown_change, sharpe_decay),
            }
        )
    return pd.DataFrame(rows).sort_values(["top_n", "oos_annualized_return"], ascending=[True, False])


def write_report(segment_metrics: pd.DataFrame, summary: pd.DataFrame, oos_ranking: pd.DataFrame) -> None:
    percent_cols = {
        "full_annualized_return",
        "full_max_drawdown",
        "is_annualized_return",
        "oos_annualized_return",
        "annualized_return_oos_minus_is",
        "is_max_drawdown",
        "oos_max_drawdown",
        "max_drawdown_oos_minus_is",
        "full_universe_annualized_return",
        "full_universe_max_drawdown",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
    }
    float_cols = {"is_sharpe_like_no_rf", "oos_sharpe_like_no_rf", "sharpe_like_no_rf"}
    summary_table = summary[[
        "strategy_name",
        "lookback_days",
        "top_n",
        "is_annualized_return",
        "oos_annualized_return",
        "annualized_return_oos_minus_is",
        "is_max_drawdown",
        "oos_max_drawdown",
        "full_universe_annualized_return",
        "stability_flag",
    ]]
    ranking_table = oos_ranking[[
        "rank_oos_return",
        "strategy_name",
        "lookback_days",
        "top_n",
        "oos_annualized_return",
        "oos_max_drawdown",
        "oos_sharpe_like_no_rf",
        "annualized_return_oos_minus_is",
        "stability_flag",
    ]]
    lines = [
        "# ETF 动量窗口 TopN 样本内/样本外稳定性验证",
        "",
        "## 参数口径",
        "",
        "- 动量窗口：1/2/3/6/9/12 月，分别近似 21/42/63/126/189/252 个交易日。",
        "- TopN：Top1、Top2、Top3。",
        "- 调仓：每月末收盘后生成信号，下一交易日目标权重生效。",
        "- 风险规则：行业/主题 ETF 有正动量则持有 TopN 正动量标的；否则切到正动量防守资产；再否则空仓。",
        f"- vectorbt 成本：佣金 `{FEE_RATE:.4%}`，滑点 `{SLIPPAGE:.4%}`。",
        "",
        "## 切分区间",
        "",
        "| 区间 | 日期 | 用途 |",
        "|---|---|---|",
        "| 全样本 | 2015-01-05 ~ 2026-06-18 | 总览，不用于最终定论 |",
        "| 样本内 | 2015-01-05 ~ 2021-12-31 | 规则探索、参数初筛 |",
        "| 样本外 | 2022-01-01 ~ 2026-06-18 | 验证规则是否还能工作 |",
        "| 完整ETF池期 | 2021-03-02 ~ 2026-06-18 | 14只行业ETF全部可用后的检查 |",
        "",
        "## 样本外排名",
        "",
        dataframe_to_markdown(ranking_table, percent_cols=percent_cols, float_cols=float_cols),
        "",
        "## 稳定性摘要",
        "",
        dataframe_to_markdown(summary_table, percent_cols=percent_cols, float_cols=float_cols),
        "",
        "## 输出文件",
        "",
        f"- 每日净值：`{DAILY_PATH.as_posix()}`",
        f"- 调仓决策：`{DECISIONS_PATH.as_posix()}`",
        f"- 全样本指标：`{FULL_METRICS_PATH.as_posix()}`",
        f"- 分区指标：`{SEGMENT_METRICS_PATH.as_posix()}`",
        f"- 稳定性摘要：`{STABILITY_SUMMARY_PATH.as_posix()}`",
        f"- 样本外排名：`{OOS_RANKING_PATH.as_posix()}`",
        "",
        "## 解读提醒",
        "",
        "- 这是候选规则稳定性筛查，不是实盘结论。",
        "- 若样本外年化明显低于样本内，说明规则可能依赖早期市场结构。",
        "- 需要继续做分年度、滚动样本外与宽基过滤验证。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    meta, close, sector_symbols, defensive_symbols, _ = load_data()
    all_daily = []
    all_decisions = []
    full_metric_rows = []
    segment_rows = []

    for window_label, lookback_days in WINDOWS:
        for top_n in TOP_N_LIST:
            decisions, target_weights = build_decisions_and_weights(
                close, meta, sector_symbols, defensive_symbols, window_label, lookback_days, top_n
            )
            pf = run_vectorbt(close, target_weights)
            value = portfolio_value_series(pf)
            nav = value / INIT_CASH
            strategy_key = f"top{top_n}_{window_label}"
            strategy_name = f"Top{top_n} {window_label}"
            daily = pd.DataFrame(
                {
                    "date": value.index,
                    "strategy_key": strategy_key,
                    "strategy_name": strategy_name,
                    "window_label": window_label,
                    "lookback_days": lookback_days,
                    "top_n": top_n,
                    "portfolio_value": value.values,
                    "nav": nav.values,
                    "daily_return": nav.pct_change().fillna(0.0).values,
                }
            )
            active_counts = target_weights.gt(0).sum(axis=1)
            orders = pf.orders.records_readable.copy()
            full_metrics = calc_metrics_from_nav(nav)
            full_metrics.update(
                {
                    "strategy_key": strategy_key,
                    "strategy_name": strategy_name,
                    "window_label": window_label,
                    "lookback_days": lookback_days,
                    "top_n": top_n,
                    "order_count": len(orders),
                    "cash_target_days": int(active_counts.eq(0).sum()),
                    "single_asset_target_days": int(active_counts.eq(1).sum()),
                    "multi_asset_target_days": int(active_counts.gt(1).sum()),
                    "risk_on_signals": int(decisions["risk_state"].eq("risk_on").sum()),
                    "defensive_signals": int(decisions["risk_state"].eq("defensive").sum()),
                    "cash_signals": int(decisions["risk_state"].eq("cash").sum()),
                }
            )
            for segment_key, segment_name, start, end in SEGMENTS:
                segment_metrics = calc_segment_metrics(daily, segment_key, segment_name, start, end)
                segment_metrics.update(
                    {
                        "strategy_key": strategy_key,
                        "strategy_name": strategy_name,
                        "window_label": window_label,
                        "lookback_days": lookback_days,
                        "top_n": top_n,
                    }
                )
                segment_rows.append(segment_metrics)
            all_daily.append(daily)
            all_decisions.append(decisions)
            full_metric_rows.append(full_metrics)

    daily_all = pd.concat(all_daily, ignore_index=True)
    decisions_all = pd.concat(all_decisions, ignore_index=True)
    full_metrics = pd.DataFrame(full_metric_rows)
    segment_metrics = pd.DataFrame(segment_rows)
    summary = build_summary(segment_metrics)
    oos_ranking = summary.sort_values(
        ["oos_annualized_return", "oos_max_drawdown", "oos_sharpe_like_no_rf"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    oos_ranking.insert(0, "rank_oos_return", np.arange(1, len(oos_ranking) + 1))

    daily_all.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    decisions_all.to_csv(DECISIONS_PATH, index=False, encoding="utf-8-sig")
    full_metrics.to_csv(FULL_METRICS_PATH, index=False, encoding="utf-8-sig")
    segment_metrics.to_csv(SEGMENT_METRICS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(STABILITY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    oos_ranking.to_csv(OOS_RANKING_PATH, index=False, encoding="utf-8-sig")
    write_report(segment_metrics, summary, oos_ranking)

    print(f"vectorbt version: {vbt.__version__}")
    print(f"Saved daily: {DAILY_PATH}")
    print(f"Saved decisions: {DECISIONS_PATH}")
    print(f"Saved full metrics: {FULL_METRICS_PATH}")
    print(f"Saved segment metrics: {SEGMENT_METRICS_PATH}")
    print(f"Saved stability summary: {STABILITY_SUMMARY_PATH}")
    print(f"Saved OOS ranking: {OOS_RANKING_PATH}")
    print(f"Saved report: {REPORT_PATH}")
    print(oos_ranking[[
        "rank_oos_return",
        "strategy_name",
        "oos_annualized_return",
        "oos_max_drawdown",
        "oos_sharpe_like_no_rf",
        "annualized_return_oos_minus_is",
        "stability_flag",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
