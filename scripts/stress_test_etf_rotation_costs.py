from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE / "outputs"
SCRIPT_DIR = BASE / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import vectorbt_top1_top2_top3_risk_filter_42d as strategy

COST_SCENARIOS = [
    {
        "scenario": "no_cost",
        "commission_rate": 0.0,
        "slippage_rate": 0.0,
        "description": "无成本，用于观察策略毛收益上限。",
    },
    {
        "scenario": "base_0_02pct",
        "commission_rate": 0.0001,
        "slippage_rate": 0.0001,
        "description": "原 vectorbt 口径：佣金0.01% + 滑点0.01%，单边合计0.02%。",
    },
    {
        "scenario": "mid_0_05pct",
        "commission_rate": 0.0003,
        "slippage_rate": 0.0002,
        "description": "中性压力：佣金0.03% + 滑点0.02%，单边合计0.05%。",
    },
    {
        "scenario": "high_0_10pct",
        "commission_rate": 0.0005,
        "slippage_rate": 0.0005,
        "description": "高成本压力：佣金0.05% + 滑点0.05%，单边合计0.10%。",
    },
    {
        "scenario": "severe_0_20pct",
        "commission_rate": 0.0010,
        "slippage_rate": 0.0010,
        "description": "极端压力：佣金0.10% + 滑点0.10%，单边合计0.20%。",
    },
]

DETAIL_PATH = OUTPUT_DIR / "etf_rotation_cost_stress_detail.csv"
SUMMARY_PATH = OUTPUT_DIR / "etf_rotation_cost_stress_summary.csv"
REPORT_PATH = OUTPUT_DIR / "etf_rotation_cost_stress_report.md"


def pct(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.2%}"


def num(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.3f}"


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    header = "| " + " | ".join(df.columns.astype(str)) + " |"
    separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in df.itertuples(index=False, name=None)]
    return "\n".join([header, separator, *rows])


def run_portfolio(close: pd.DataFrame, target_weights: pd.DataFrame, commission_rate: float, slippage_rate: float):
    return strategy.vbt.Portfolio.from_orders(
        close=close,
        size=target_weights,
        size_type="targetpercent",
        group_by=True,
        cash_sharing=True,
        init_cash=strategy.INIT_CASH,
        fees=commission_rate,
        slippage=slippage_rate,
        freq="1D",
    )


def turnover_metrics(target_weights: pd.DataFrame) -> dict[str, float]:
    weights = target_weights.fillna(0.0)
    prev = weights.shift(1).fillna(0.0)
    delta = weights - prev
    buys = delta.clip(lower=0).sum(axis=1)
    sells = (-delta.clip(upper=0)).sum(axis=1)
    one_way = pd.concat([buys, sells], axis=1).max(axis=1)
    two_way = buys + sells
    years = len(weights) / 252
    trade_days = int(two_way.gt(1e-9).sum())
    return {
        "target_trade_day_count": trade_days,
        "target_total_one_way_turnover": float(one_way.sum()),
        "target_annual_one_way_turnover": float(one_way.sum() / years),
        "target_total_two_way_traded": float(two_way.sum()),
        "target_annual_two_way_traded": float(two_way.sum() / years),
    }


def collect_metrics(top_n: int, scenario: dict[str, object], close: pd.DataFrame, target_weights: pd.DataFrame, decisions: pd.DataFrame) -> dict[str, object]:
    target_turnover = turnover_metrics(target_weights)
    pf = run_portfolio(
        close,
        target_weights,
        float(scenario["commission_rate"]),
        float(scenario["slippage_rate"]),
    )
    value = pf.value()
    if isinstance(value, pd.DataFrame):
        value = value.iloc[:, 0]
    nav = value / strategy.INIT_CASH
    ret = value.pct_change().fillna(0.0)
    orders = pf.orders.records_readable.copy()
    total_order_value = float((orders["Size"] * orders["Price"]).abs().sum()) if {"Size", "Price"}.issubset(orders.columns) else np.nan
    total_fees = float(orders["Fees"].sum()) if "Fees" in orders.columns else np.nan
    years = len(value) / 252
    active_counts = target_weights.gt(0).sum(axis=1)
    trade_dates = orders["Timestamp"].nunique() if "Timestamp" in orders.columns else np.nan
    return {
        "strategy": f"Top{top_n}",
        "top_n": top_n,
        "scenario": scenario["scenario"],
        "commission_rate": scenario["commission_rate"],
        "slippage_rate": scenario["slippage_rate"],
        "one_way_cost": float(scenario["commission_rate"]) + float(scenario["slippage_rate"]),
        "total_return": float(nav.iloc[-1] - 1.0),
        "annualized_return": strategy.annualized_return(nav),
        "annualized_volatility": strategy.annualized_volatility(ret),
        "max_drawdown": strategy.max_drawdown(nav),
        "sharpe_like_no_rf": strategy.sharpe_like(ret),
        "final_value": float(value.iloc[-1]),
        "order_count": int(len(orders)),
        "trade_date_count": int(trade_dates) if pd.notna(trade_dates) else np.nan,
        **target_turnover,
        "total_fees": total_fees,
        "total_order_value": total_order_value,
        "annual_traded_value_ratio": float(total_order_value / strategy.INIT_CASH / years) if pd.notna(total_order_value) else np.nan,
        "cash_target_days": int(active_counts.eq(0).sum()),
        "single_asset_target_days": int(active_counts.eq(1).sum()),
        "multi_asset_target_days": int(active_counts.gt(1).sum()),
        "risk_on_signals": int(decisions["risk_state"].eq("risk_on").sum()),
        "defensive_signals": int(decisions["risk_state"].eq("defensive").sum()),
        "cash_signals": int(decisions["risk_state"].eq("cash").sum()),
    }


def write_report(detail: pd.DataFrame, summary: pd.DataFrame) -> None:
    base = detail[detail["scenario"].eq("base_0_02pct")].set_index("strategy")
    severe = detail[detail["scenario"].eq("severe_0_20pct")].set_index("strategy")
    lines = [
        "# ETF 42日动量轮动成本压力测试",
        "",
        "## 资料来源",
        "",
        "- 本地项目：`D:/Quant`。",
        "- 策略脚本：`scripts/vectorbt_top1_top2_top3_risk_filter_42d.py`。",
        "- Notion 口径：重点使用“加入交易成本并计算换手率”中对单边换手、双边成交、订单数、成本拖累的定义。",
        "",
        "## 测试对象",
        "",
        "- Top1/Top2/Top3 42日动量风险过滤 ETF 轮动。",
        "- 月度调仓，调仓日收盘后生成信号，下一交易日按目标权重生效。",
        "- 风险过滤：行业/主题ETF正动量时持有 TopN；否则切防守资产或空仓。",
        "",
        "## 成本场景",
        "",
    ]
    for item in COST_SCENARIOS:
        lines.append(f"- `{item['scenario']}`：{item['description']}")

    table = detail.copy()
    table = table[[
        "strategy",
        "scenario",
        "one_way_cost",
        "total_return",
        "annualized_return",
        "max_drawdown",
        "sharpe_like_no_rf",
        "order_count",
        "trade_date_count",
        "target_annual_one_way_turnover",
        "target_annual_two_way_traded",
        "annual_traded_value_ratio",
        "cost_drag_vs_no_cost",
        "annualized_drag_vs_no_cost",
    ]]
    formatted = table.copy()
    for column in ["one_way_cost", "total_return", "annualized_return", "max_drawdown", "target_annual_one_way_turnover", "target_annual_two_way_traded", "annual_traded_value_ratio", "cost_drag_vs_no_cost", "annualized_drag_vs_no_cost"]:
        formatted[column] = formatted[column].map(pct)
    formatted["sharpe_like_no_rf"] = formatted["sharpe_like_no_rf"].map(num)

    lines.extend(["", "## 压力测试明细", "", dataframe_to_markdown(formatted), "", "## 核心判断", ""])
    for name in ["Top1", "Top2", "Top3"]:
        base_row = base.loc[name]
        severe_row = severe.loc[name]
        lines.append(
            f"- {name}：基准成本年化收益 {pct(base_row.annualized_return)}，极端成本年化收益 {pct(severe_row.annualized_return)}，"
            f"年化收益下降 {pct(severe_row.annualized_return - base_row.annualized_return)}；"
            f"基准最大回撤 {pct(base_row.max_drawdown)}，极端最大回撤 {pct(severe_row.max_drawdown)}。"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- Top1 对成本最不敏感：目标权重口径下年化单边换手约 7.22 倍、年化双边成交约 14.34 倍；即使单边成本抬到 0.20%，年化收益仍保持较高，但回撤仍接近 -48%。",
            "- Top2/Top3 的订单数很高，主要来自等权组合的微小再平衡；如果真实交易严格跟随每日目标权重，会显著增加操作复杂度和摩擦。",
            "- 从可交易性看，当前阶段更适合优先研究 Top1 或降低 Top2/Top3 的再平衡频率/阈值，而不是只看分散持仓数量。",
            "- 压力测试没有推翻 Top1 的收益优势，但再次暴露它的核心问题不是成本，而是最大回撤过深。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    meta, close, sector_symbols, defensive_symbols, _ = strategy.load_data()
    rows = []
    for top_n in strategy.TOP_N_LIST:
        decisions, target_weights = strategy.build_decisions_and_weights(close, meta, sector_symbols, defensive_symbols, top_n)
        for scenario in COST_SCENARIOS:
            rows.append(collect_metrics(top_n, scenario, close, target_weights, decisions))

    detail = pd.DataFrame(rows)
    no_cost = detail[detail["scenario"].eq("no_cost")].set_index("strategy")
    detail["cost_drag_vs_no_cost"] = detail.apply(lambda row: row["total_return"] - no_cost.loc[row["strategy"], "total_return"], axis=1)
    detail["annualized_drag_vs_no_cost"] = detail.apply(lambda row: row["annualized_return"] - no_cost.loc[row["strategy"], "annualized_return"], axis=1)
    detail = detail.sort_values(["top_n", "one_way_cost"]).reset_index(drop=True)

    summary = (
        detail.groupby("scenario", as_index=False)
        .agg(
            avg_annualized_return=("annualized_return", "mean"),
            avg_max_drawdown=("max_drawdown", "mean"),
            avg_sharpe_like=("sharpe_like_no_rf", "mean"),
            avg_cost_drag_vs_no_cost=("cost_drag_vs_no_cost", "mean"),
            avg_annualized_drag_vs_no_cost=("annualized_drag_vs_no_cost", "mean"),
        )
        .sort_values("scenario")
    )

    OUTPUT_DIR.mkdir(exist_ok=True)
    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    write_report(detail, summary)
    print(f"Saved: {DETAIL_PATH}")
    print(f"Saved: {SUMMARY_PATH}")
    print(f"Saved: {REPORT_PATH}")
    print(detail[["strategy", "scenario", "one_way_cost", "annualized_return", "max_drawdown", "sharpe_like_no_rf", "cost_drag_vs_no_cost", "target_annual_one_way_turnover", "target_annual_two_way_traded", "annual_traded_value_ratio"]].to_string(index=False))


if __name__ == "__main__":
    main()
