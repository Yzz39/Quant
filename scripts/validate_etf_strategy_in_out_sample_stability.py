from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

SEGMENTS = [
    ("full_sample", "全样本", "2015-01-05", "2026-06-18"),
    ("in_sample", "样本内", "2015-01-05", "2021-12-31"),
    ("out_of_sample", "样本外", "2022-01-01", "2026-06-18"),
    ("full_universe", "完整ETF池期", "2021-03-02", "2026-06-18"),
]

STRATEGIES = [
    ("top1_42d", "Top1 42日", OUTPUT_DIR / "etf_top1_rotation_vectorbt_daily_value.csv"),
    ("top2_42d", "Top2等权 42日", OUTPUT_DIR / "etf_top2_equal_weight_rotation_vectorbt_daily_value.csv"),
    ("top3_42d", "Top3等权 42日", OUTPUT_DIR / "etf_top3_equal_weight_rotation_vectorbt_daily_value.csv"),
    ("top1_risk_filter_42d", "Top1风险过滤 42日", OUTPUT_DIR / "etf_top1_risk_filter_42d_vectorbt_daily_value.csv"),
    ("top2_risk_filter_42d", "Top2风险过滤 42日", OUTPUT_DIR / "etf_top2_risk_filter_42d_vectorbt_daily_value.csv"),
    ("top3_risk_filter_42d", "Top3风险过滤 42日", OUTPUT_DIR / "etf_top3_risk_filter_42d_vectorbt_daily_value.csv"),
]

SEGMENT_METRICS_PATH = OUTPUT_DIR / "etf_strategy_stability_in_out_sample_metrics.csv"
SUMMARY_PATH = OUTPUT_DIR / "etf_strategy_stability_in_out_sample_summary.csv"
REPORT_PATH = OUTPUT_DIR / "etf_strategy_stability_in_out_sample_report.md"


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


def calc_segment_metrics(df: pd.DataFrame, segment_key: str, segment_name: str, start: str, end: str) -> dict[str, object]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    segment = df[(df["date"] >= start_ts) & (df["date"] <= end_ts)].copy()
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
    ret = nav.pct_change().fillna(0.0)
    return {
        "segment_key": segment_key,
        "segment_name": segment_name,
        "segment_start": start,
        "segment_end": end,
        "actual_start": segment["date"].iloc[0].date().isoformat(),
        "actual_end": segment["date"].iloc[-1].date().isoformat(),
        "trading_days": len(segment),
        "total_return": float(nav.iloc[-1] / nav.iloc[0] - 1.0),
        "annualized_return": annualized_return(nav),
        "annualized_volatility": annualized_volatility(ret),
        "max_drawdown": max_drawdown(nav),
        "sharpe_like_no_rf": sharpe_like(ret),
    }


def load_strategy_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    required = {"date", "nav"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")
    return df.sort_values("date")


def build_segment_metrics() -> pd.DataFrame:
    rows = []
    for strategy_key, strategy_name, path in STRATEGIES:
        if not path.exists():
            raise FileNotFoundError(path)
        daily = load_strategy_daily(path)
        for segment_key, segment_name, start, end in SEGMENTS:
            row = calc_segment_metrics(daily, segment_key, segment_name, start, end)
            row.update(
                {
                    "strategy_key": strategy_key,
                    "strategy_name": strategy_name,
                    "source_file": path.name,
                }
            )
            rows.append(row)
    columns = [
        "strategy_key",
        "strategy_name",
        "segment_key",
        "segment_name",
        "segment_start",
        "segment_end",
        "actual_start",
        "actual_end",
        "trading_days",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
        "sharpe_like_no_rf",
        "source_file",
    ]
    return pd.DataFrame(rows)[columns]


def build_summary(metrics: pd.DataFrame) -> pd.DataFrame:
    pivot = metrics.pivot(index=["strategy_key", "strategy_name"], columns="segment_key")
    rows = []
    for strategy_key, strategy_name in metrics[["strategy_key", "strategy_name"]].drop_duplicates().itertuples(index=False):
        strategy_metrics = metrics[metrics["strategy_key"].eq(strategy_key)].set_index("segment_key")
        full = strategy_metrics.loc["full_sample"]
        ins = strategy_metrics.loc["in_sample"]
        oos = strategy_metrics.loc["out_of_sample"]
        full_universe = strategy_metrics.loc["full_universe"]
        annualized_decay = oos["annualized_return"] - ins["annualized_return"]
        drawdown_change = oos["max_drawdown"] - ins["max_drawdown"]
        sharpe_decay = oos["sharpe_like_no_rf"] - ins["sharpe_like_no_rf"]
        rows.append(
            {
                "strategy_key": strategy_key,
                "strategy_name": strategy_name,
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
    return pd.DataFrame(rows).sort_values(["oos_annualized_return", "oos_max_drawdown"], ascending=[False, False])


def classify_stability(annualized_decay: float, drawdown_change: float, sharpe_decay: float) -> str:
    if pd.isna(annualized_decay) or pd.isna(drawdown_change) or pd.isna(sharpe_decay):
        return "数据不足"
    severe_return_decay = annualized_decay < -0.15
    severe_drawdown_worse = drawdown_change < -0.10
    severe_sharpe_decay = sharpe_decay < -0.40
    if severe_return_decay and (severe_drawdown_worse or severe_sharpe_decay):
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


def write_report(metrics: pd.DataFrame, summary: pd.DataFrame) -> None:
    segment_table = metrics[[
        "strategy_name",
        "segment_name",
        "trading_days",
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
        "sharpe_like_no_rf",
    ]].copy()
    summary_table = summary[[
        "strategy_name",
        "is_annualized_return",
        "oos_annualized_return",
        "annualized_return_oos_minus_is",
        "is_max_drawdown",
        "oos_max_drawdown",
        "max_drawdown_oos_minus_is",
        "is_sharpe_like_no_rf",
        "oos_sharpe_like_no_rf",
        "stability_flag",
    ]].copy()

    percent_cols = {
        "total_return",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
        "is_annualized_return",
        "oos_annualized_return",
        "annualized_return_oos_minus_is",
        "is_max_drawdown",
        "oos_max_drawdown",
        "max_drawdown_oos_minus_is",
    }
    float_cols = {"sharpe_like_no_rf", "is_sharpe_like_no_rf", "oos_sharpe_like_no_rf"}

    lines = [
        "# ETF 策略样本内/样本外稳定性验证",
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
        "## 稳定性摘要",
        "",
        dataframe_to_markdown(summary_table, percent_cols=percent_cols, float_cols=float_cols),
        "",
        "## 分区完整指标",
        "",
        dataframe_to_markdown(segment_table, percent_cols=percent_cols, float_cols=float_cols),
        "",
        "## 输出文件",
        "",
        f"- 分区指标：`{SEGMENT_METRICS_PATH.as_posix()}`",
        f"- 稳定性摘要：`{SUMMARY_PATH.as_posix()}`",
        f"- Markdown 报告：`{REPORT_PATH.as_posix()}`",
        "",
        "## 解读提醒",
        "",
        "- 样本外表现低于样本内，不一定代表策略失效；需要结合市场阶段、回撤、波动和交易成本看。",
        "- 风险过滤 42日版本与原 Top1/Top2/Top3 目前逻辑一致，因此稳定性结果也应一致。",
        "- 完整ETF池期从 2021-03-02 开始，因为最晚纳入的行业ETF从这天才有数据。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metrics = build_segment_metrics()
    summary = build_summary(metrics)
    metrics.to_csv(SEGMENT_METRICS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    write_report(metrics, summary)

    print(f"Saved segment metrics: {SEGMENT_METRICS_PATH}")
    print(f"Saved stability summary: {SUMMARY_PATH}")
    print(f"Saved report: {REPORT_PATH}")
    print(summary[[
        "strategy_name",
        "is_annualized_return",
        "oos_annualized_return",
        "annualized_return_oos_minus_is",
        "is_max_drawdown",
        "oos_max_drawdown",
        "stability_flag",
    ]].to_string(index=False))


if __name__ == "__main__":
    main()
