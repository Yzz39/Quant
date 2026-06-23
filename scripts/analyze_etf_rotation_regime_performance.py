from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE / "outputs"
CLOSE_PATH = BASE / "data" / "etf_momentum_close_wide_qfq.csv"
DETAIL_PATH = OUTPUT_DIR / "etf_rotation_regime_performance_detail.csv"
SUMMARY_PATH = OUTPUT_DIR / "etf_rotation_regime_performance_summary.md"

TRADING_DAYS = 252
BENCHMARK_SYMBOL = "510300"
STRATEGIES = {
    "Top1": OUTPUT_DIR / "etf_top1_risk_filter_42d_vectorbt_daily_value.csv",
    "Top2": OUTPUT_DIR / "etf_top2_risk_filter_42d_vectorbt_daily_value.csv",
    "Top3": OUTPUT_DIR / "etf_top3_risk_filter_42d_vectorbt_daily_value.csv",
}

REGIME_PERIODS = [
    ("2015杠杆牛熊", "2015-04-01", "2016-02-29", "急涨急跌，检验追涨后抗回撤能力"),
    ("2016-2017蓝筹慢牛", "2016-03-01", "2017-12-31", "低波动修复与蓝筹占优"),
    ("2018熊市", "2018-01-01", "2018-12-31", "系统性下跌，检验防守能力"),
    ("2019-2021结构牛", "2019-01-01", "2021-12-31", "成长、消费、新能源等结构性机会"),
    ("2022熊市", "2022-01-01", "2022-12-31", "成长回撤与风险偏好收缩"),
    ("2023震荡弱市", "2023-01-01", "2023-12-31", "指数弱、主题轮动快"),
    ("2024-2026恢复期", "2024-01-01", "2026-06-18", "政策与流动性修复阶段"),
]


def max_drawdown(nav: pd.Series) -> float:
    nav = nav.dropna()
    if nav.empty:
        return np.nan
    return float((nav / nav.cummax() - 1.0).min())


def annualized_return(ret: pd.Series) -> float:
    ret = ret.dropna()
    if ret.empty:
        return np.nan
    total = float((1.0 + ret).prod() - 1.0)
    years = len(ret) / TRADING_DAYS
    if years <= 0 or total <= -1:
        return np.nan
    return float((1.0 + total) ** (1.0 / years) - 1.0)


def annualized_volatility(ret: pd.Series) -> float:
    ret = ret.dropna()
    if ret.empty:
        return np.nan
    return float(ret.std(ddof=0) * np.sqrt(TRADING_DAYS))


def sharpe_like(ret: pd.Series) -> float:
    vol = annualized_volatility(ret)
    if pd.isna(vol) or vol == 0:
        return np.nan
    return float(ret.mean() * TRADING_DAYS / vol)


def calc_metrics(ret: pd.Series) -> dict[str, float]:
    ret = ret.dropna()
    nav = (1.0 + ret).cumprod()
    total = float(nav.iloc[-1] - 1.0) if not nav.empty else np.nan
    mdd = max_drawdown(nav)
    ann = annualized_return(ret)
    return {
        "days": int(len(ret)),
        "total_return": total,
        "annualized_return": ann,
        "annualized_volatility": annualized_volatility(ret),
        "max_drawdown": mdd,
        "sharpe_like_no_rf": sharpe_like(ret),
        "calmar": float(ann / abs(mdd)) if pd.notna(ann) and pd.notna(mdd) and mdd < 0 else np.nan,
        "positive_day_ratio": float((ret > 0).mean()) if len(ret) else np.nan,
    }


def pct(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.2%}"


def num(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.2f}"


def md_table(df: pd.DataFrame) -> str:
    header = "| " + " | ".join(df.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows = ["| " + " | ".join(str(x) for x in row) + " |" for row in df.itertuples(index=False, name=None)]
    return "\n".join([header, sep, *rows])


def load_returns() -> pd.DataFrame:
    close = pd.read_csv(CLOSE_PATH, parse_dates=["date"], dtype={"date": "string"})
    close["date"] = pd.to_datetime(close["date"])
    close = close.set_index("date").sort_index()
    benchmark_ret = close[BENCHMARK_SYMBOL].astype(float).pct_change().fillna(0.0)

    returns = pd.DataFrame({"benchmark_510300": benchmark_ret})
    for name, path in STRATEGIES.items():
        daily = pd.read_csv(path, parse_dates=["date"])
        daily = daily.set_index("date").sort_index()
        returns[name] = pd.to_numeric(daily["daily_return"], errors="coerce").fillna(0.0)
    return returns.dropna(how="all")


def classify_years(benchmark_ret: pd.Series) -> list[tuple[str, str, str, str]]:
    yearly = benchmark_ret.groupby(benchmark_ret.index.year).apply(lambda s: float((1.0 + s).prod() - 1.0))
    regimes = []
    for year, value in yearly.items():
        if value >= 0.15:
            label = "基准上涨年"
        elif value <= -0.15:
            label = "基准下跌年"
        else:
            label = "基准震荡年"
        regimes.append((f"{int(year)} {label}", f"{int(year)}-01-01", f"{int(year)}-12-31", f"510300全年收益 {pct(value)}"))
    return regimes


def main() -> None:
    returns = load_returns()
    rows = []
    regimes = REGIME_PERIODS + classify_years(returns["benchmark_510300"])

    for regime, start, end, description in regimes:
        mask = returns.index.to_series().between(pd.Timestamp(start), pd.Timestamp(end))
        part = returns.loc[mask]
        if part.empty:
            continue
        bench_metrics = calc_metrics(part["benchmark_510300"])
        for strategy in ["Top1", "Top2", "Top3"]:
            metrics = calc_metrics(part[strategy])
            row = {
                "regime": regime,
                "description": description,
                "start": part.index.min().date().isoformat(),
                "end": part.index.max().date().isoformat(),
                "strategy": strategy,
                "benchmark_total_return": bench_metrics["total_return"],
                "benchmark_max_drawdown": bench_metrics["max_drawdown"],
            }
            row.update(metrics)
            row["excess_total_return"] = row["total_return"] - bench_metrics["total_return"]
            row["drawdown_improvement"] = row["max_drawdown"] - bench_metrics["max_drawdown"]
            rows.append(row)

    detail = pd.DataFrame(rows)
    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")

    macro = detail[detail["regime"].isin([x[0] for x in REGIME_PERIODS])].copy()
    table = macro[[
        "regime",
        "strategy",
        "benchmark_total_return",
        "total_return",
        "excess_total_return",
        "max_drawdown",
        "drawdown_improvement",
        "annualized_return",
        "sharpe_like_no_rf",
        "calmar",
    ]].copy()
    for column in [
        "benchmark_total_return",
        "total_return",
        "excess_total_return",
        "max_drawdown",
        "drawdown_improvement",
        "annualized_return",
    ]:
        table[column] = table[column].map(pct)
    for column in ["sharpe_like_no_rf", "calmar"]:
        table[column] = table[column].map(num)

    best_by_regime = macro.sort_values(["regime", "calmar", "total_return"], ascending=[True, False, False]).groupby("regime", sort=False).head(1)
    best_table = best_by_regime[["regime", "strategy", "total_return", "max_drawdown", "annualized_return", "sharpe_like_no_rf", "calmar"]].copy()
    for column in ["total_return", "max_drawdown", "annualized_return"]:
        best_table[column] = best_table[column].map(pct)
    for column in ["sharpe_like_no_rf", "calmar"]:
        best_table[column] = best_table[column].map(num)

    yearly = detail[detail["regime"].str.contains("基准")].copy()
    yearly_summary = (
        yearly.groupby("strategy")
        .agg(
            median_excess=("excess_total_return", "median"),
            median_drawdown_improvement=("drawdown_improvement", "median"),
            worst_regime_return=("total_return", "min"),
            worst_regime_drawdown=("max_drawdown", "min"),
            positive_regime_count=("total_return", lambda s: int((s > 0).sum())),
            regime_count=("total_return", "count"),
        )
        .reset_index()
    )
    yearly_summary["positive_regime_ratio"] = yearly_summary["positive_regime_count"] / yearly_summary["regime_count"]
    yearly_table = yearly_summary.copy()
    for column in ["median_excess", "median_drawdown_improvement", "worst_regime_return", "worst_regime_drawdown", "positive_regime_ratio"]:
        yearly_table[column] = yearly_table[column].map(pct)

    lines = [
        "# ETF 42日动量风险过滤轮动：不同市场环境表现分析",
        "",
        "## 口径",
        "",
        "- 策略：Top1/Top2/Top3 42日动量 + 风险过滤，使用现有 vectorbt 日净值结果。",
        "- 成本：沿用已有回测基准口径，佣金0.01% + 滑点0.01%，单边合计0.02%。",
        "- 基准：510300 沪深300ETF。",
        "- 指标：收益、年化、最大回撤、夏普近似、Calmar；超额=策略收益-基准收益，回撤改善=策略回撤-基准回撤，数值越大越好。",
        "",
        "## 大阶段表现",
        "",
        md_table(table),
        "",
        "## 每个市场环境下的最优 TopN（优先 Calmar，其次收益）",
        "",
        md_table(best_table),
        "",
        "## 按自然年市场状态汇总",
        "",
        md_table(yearly_table),
        "",
        "## 核心观察",
        "",
    ]

    for strategy in ["Top1", "Top2", "Top3"]:
        sub = macro[macro["strategy"].eq(strategy)]
        best = sub.sort_values(["total_return"], ascending=False).iloc[0]
        worst = sub.sort_values(["total_return"], ascending=True).iloc[0]
        lines.append(
            f"- {strategy}：最好阶段是{best.regime}，总收益 {pct(best.total_return)}，最大回撤 {pct(best.max_drawdown)}；"
            f"最差阶段是{worst.regime}，总收益 {pct(worst.total_return)}，最大回撤 {pct(worst.max_drawdown)}。"
        )

    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- Top1 在趋势和结构性机会阶段进攻性最强，但急跌阶段和2023震荡弱市的回撤压力也最大。",
            "- Top2 通常是更均衡的折中：收益低于Top1，但在部分震荡/恢复阶段的回撤和Calmar更稳。",
            "- Top3 分散后收益被明显摊薄，并没有稳定换来更小回撤；至少在当前参数下不是最优主线。",
            "- 策略真正怕的不是单边成本，而是高位切换失败与快速风格轮动。后续优化重点应放在风控过滤、调仓阈值和止损/降仓规则，而不是只纠结TopN数量。",
        ]
    )
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved: {DETAIL_PATH}")
    print(f"Saved: {SUMMARY_PATH}")
    print(best_table.to_string(index=False))


if __name__ == "__main__":
    main()
