from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE / "outputs"
REPORT_PATH = OUTPUT_DIR / "parameter_visualization_return_risk_evaluation.md"
CHECKLIST_PATH = OUTPUT_DIR / "parameter_visualization_metric_checklist.csv"


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUT_DIR / name)


def md_table(df: pd.DataFrame) -> str:
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


def select(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    return df[[col for col in cols if col in df.columns]].copy()


def build_metric_checklist() -> pd.DataFrame:
    rows = [
        {
            "category": "收益",
            "metric": "annualized_return",
            "meaning": "把历史总收益折算成年化，用于不同样本长度比较。",
            "watch_out": "不能单独用它选参数；高年化可能来自高回撤、高换手或样本内过拟合。",
            "decision_use": "作为第一层排序指标，但必须和回撤、夏普、样本外一起看。",
        },
        {
            "category": "收益",
            "metric": "total_return / final_nav",
            "meaning": "全样本累计收益或最终净值。",
            "watch_out": "样本越长越容易放大复利差异；容易诱导选择历史单点赢家。",
            "decision_use": "用于直观理解长期复利结果，不用于单独决策。",
        },
        {
            "category": "风险",
            "metric": "max_drawdown",
            "meaning": "从历史高点到低点的最大跌幅，代表最痛苦区间。",
            "watch_out": "高收益参数如果最大回撤过深，可能不符合慢慢复利目标。",
            "decision_use": "优先排除回撤超出承受范围的参数。",
        },
        {
            "category": "风险",
            "metric": "annualized_volatility",
            "meaning": "收益波动的年化标准差。",
            "watch_out": "低波动不等于低回撤；趋势策略可能长时间平稳后突然回撤。",
            "decision_use": "配合回撤和夏普判断收益是否靠高波动换来。",
        },
        {
            "category": "收益风险比",
            "metric": "sharpe_like_no_rf",
            "meaning": "不扣无风险利率的类夏普，衡量单位波动获得的收益。",
            "watch_out": "非正态收益、跳空和长回撤会让夏普显得过于乐观。",
            "decision_use": "寻找收益/波动更平衡的参数区域。",
        },
        {
            "category": "收益风险比",
            "metric": "calmar",
            "meaning": "年化收益 / 最大回撤绝对值，更贴近回撤承受能力。",
            "watch_out": "依赖单个最大回撤点，样本变动会改变数值。",
            "decision_use": "适合和最大回撤一起筛选候选参数。",
        },
        {
            "category": "交易摩擦",
            "metric": "trade_count / order_count",
            "meaning": "调仓次数或订单行数。",
            "watch_out": "订单数不是换手率；等权组合会产生很多小额再平衡订单。",
            "decision_use": "用于评估执行复杂度，不能替代换手指标。",
        },
        {
            "category": "交易摩擦",
            "metric": "annual_one_way_turnover / annual_two_way_traded",
            "meaning": "年化单边换手和双边成交，衡量资金被替换的程度。",
            "watch_out": "高换手参数更容易被滑点、最小佣金和冲击成本侵蚀。",
            "decision_use": "收益相近时优先选择换手更低的参数。",
        },
        {
            "category": "成本",
            "metric": "cost_drag / total_estimated_cost",
            "meaning": "交易成本对净值的拖累。",
            "watch_out": "当前成本未完全包含小资金最低5元佣金和真实盘口冲击。",
            "decision_use": "判断高收益是否靠过度交易堆出来。",
        },
        {
            "category": "稳健性",
            "metric": "oos_annualized_return / annualized_return_oos_minus_is",
            "meaning": "样本外年化和样本外相对样本内退化幅度。",
            "watch_out": "样本内冠军如果样本外大幅退化，过拟合嫌疑高。",
            "decision_use": "优先选择样本外仍为正、退化较小的参数区域。",
        },
    ]
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    full_metrics = read_csv("etf_momentum_windows_topn_vectorbt_full_metrics.csv")
    oos_summary = read_csv("etf_momentum_windows_topn_in_out_sample_summary.csv")
    oos_ranking = read_csv("etf_momentum_windows_topn_oos_ranking.csv")
    frequency_summary = read_csv("etf_momentum_rebalance_frequency_summary.csv")
    frequency_detail = read_csv("etf_momentum_rebalance_frequency_comparison_metrics.csv")
    window_1to6 = read_csv("etf_momentum_1to6_month_comparison_metrics.csv")
    sma_scan = read_csv("sma_trend_parameter_scan.csv")

    checklist = build_metric_checklist()
    checklist.to_csv(CHECKLIST_PATH, index=False, encoding="utf-8-sig")

    top_full_return = full_metrics.sort_values("annualized_return", ascending=False).head(8)
    top_full_balance = full_metrics.assign(
        drawdown_abs=full_metrics["max_drawdown"].abs(),
        return_drawdown_ratio=full_metrics["annualized_return"] / full_metrics["max_drawdown"].abs(),
    ).sort_values(["return_drawdown_ratio", "sharpe_like_no_rf"], ascending=False).head(8)
    oos_top = oos_ranking.head(10)
    oos_stable = oos_summary.sort_values(["stability_flag", "oos_annualized_return"], ascending=[True, False]).head(10)
    bad_degradation = oos_summary.sort_values("annualized_return_oos_minus_is").head(8)
    freq_view = select(
        frequency_summary,
        [
            "rebalance_frequency",
            "avg_annualized_return",
            "avg_max_drawdown",
            "avg_sharpe_like",
            "avg_annual_one_way_turnover",
            "avg_cost_drag",
            "best_annualized_return",
            "worst_annualized_return",
        ],
    )
    freq_detail_view = select(
        frequency_detail.sort_values("annualized_return", ascending=False).head(10),
        [
            "window_label",
            "rebalance_frequency",
            "annualized_return",
            "max_drawdown",
            "sharpe_like_no_rf",
            "trade_count",
            "annual_one_way_turnover",
            "cost_drag",
        ],
    )
    sma_view = select(
        sma_scan.sort_values(["symbol", "annualized_return"], ascending=[True, False]),
        ["symbol", "name", "sma_window", "annualized_return", "max_drawdown", "sharpe", "calmar", "trades", "time_in_market"],
    )

    lines = [
        "# 参数可视化的收益和风险指标评估",
        "",
        "## 结论摘要",
        "",
        "参数可视化的目标不是找历史收益最高的单个参数，而是识别一片相对稳定、风险可承受、交易成本可解释、样本外不崩的参数区域。当前 ETF 动量参数结果显示：2个月/6个月窗口在全样本较强，但样本外退化明显；月度调仓在收益和执行负担之间更适合继续研究；单看年化收益会高估部分参数的可靠性。",
        "",
        "## 1. 指标分层：先看什么，后看什么",
        "",
        md_table(checklist),
        "",
        "## 2. 全样本收益冠军不等于可靠参数",
        "",
        "全样本年化收益最高的参数可以作为观察对象，但不能直接作为最终选择。比如 Top1 2m 全样本年化最高，但它集中度高，且样本外明显退化。",
        "",
        md_table(select(top_full_return, ["strategy_name", "window_label", "top_n", "annualized_return", "annualized_volatility", "max_drawdown", "sharpe_like_no_rf", "order_count", "cash_target_days"])),
        "",
        "## 3. 收益/回撤平衡视角",
        "",
        "更接近实用决策的是收益与回撤的平衡，而不是收益孤峰。这里用 `annualized_return / abs(max_drawdown)` 做一个简化排序，帮助观察哪些参数不是靠极端回撤换收益。",
        "",
        md_table(select(top_full_balance, ["strategy_name", "window_label", "top_n", "annualized_return", "max_drawdown", "return_drawdown_ratio", "sharpe_like_no_rf"])),
        "",
        "## 4. 样本外评估：最重要的风险指标",
        "",
        "样本外指标回答的是：如果不在最舒服的历史区间里，这个参数还能不能活。当前结果里，短窗口和全样本高收益参数普遍有明显退化，说明参数可视化必须加入样本外视角。",
        "",
        md_table(select(oos_top, ["rank_oos_return", "strategy_name", "full_annualized_return", "is_annualized_return", "oos_annualized_return", "oos_max_drawdown", "annualized_return_oos_minus_is", "stability_flag"])),
        "",
        "## 5. 样本外退化最大的参数",
        "",
        "这些参数在样本内和样本外之间落差较大，是过拟合或市场环境切换的重点警示对象。",
        "",
        md_table(select(bad_degradation, ["strategy_name", "is_annualized_return", "oos_annualized_return", "annualized_return_oos_minus_is", "is_sharpe_like_no_rf", "oos_sharpe_like_no_rf", "sharpe_oos_minus_is", "stability_flag"])),
        "",
        "## 6. 调仓频率：收益、风险和换手一起看",
        "",
        "高频调仓不一定更好。周度和双周可能提高部分参数收益，但也显著提高换手、订单和成本；季度换手低，但收益下降。月度调仓目前更适合作为学习和纸面交易的默认频率。",
        "",
        md_table(freq_view),
        "",
        "## 7. 参数组合中的高收益与高换手",
        "",
        "如果一个参数组合收益高但换手也高，就要警惕它在真实交易中被滑点和最低佣金吃掉。收益相近时，优先选择换手更低、成本拖累更小的组合。",
        "",
        md_table(freq_detail_view),
        "",
        "## 8. 1到6个月动量窗口的风险收益解读",
        "",
        "1到6个月窗口不是平滑递增关系：2个月和6个月较强，3个月明显较弱。参数曲线不平滑，说明不能因为某个窗口好就假设邻近窗口也好，必须看稳定区域。",
        "",
        md_table(select(window_1to6, ["window_label", "lookback_days", "annualized_return", "annualized_volatility", "max_drawdown", "sharpe_like_no_rf", "trade_count", "cash_days", "defensive_days", "sector_days"])),
        "",
        "## 9. SMA 参数扫描的对照意义",
        "",
        "SMA 单资产扫描显示，不同窗口在不同 ETF 上差异很大，且部分结果为负。这提醒我们：参数可视化不仅用于选参数，也用于发现策略假设是否脆弱。",
        "",
        md_table(sma_view.head(15)),
        "",
        "## 10. 如何阅读一张参数热力图或曲线",
        "",
        "1. 先看收益：年化收益是否为正，是否明显优于基准。",
        "2. 再看风险：最大回撤是否在可承受范围内，波动是否过高。",
        "3. 看收益风险比：夏普/Calmar 是否比基准更好。",
        "4. 看交易摩擦：换手、订单、成本拖累是否合理。",
        "5. 看稳定性：邻近参数是否也表现不错，还是只有一个孤峰。",
        "6. 看样本外：样本外是否仍为正，退化是否可接受。",
        "",
        "## 11. 当前参数评估结论",
        "",
        "- `Top1 2m`：全样本收益高，但集中度高，样本外明显退化，不适合作为保守基线。",
        "- `Top2 2m / 42日`：全样本收益风险较好，适合作为候选基线，但样本外退化明显，需要纸面交易和滚动验证。",
        "- `Top2 9m`：样本外退化较小、稳定性较好，可作为稳健性对照。",
        "- `Top3`：分散度提高，但收益下降明显，回撤改善不够，暂时不是最优先候选。",
        "- `月度调仓`：收益和执行成本之间较均衡，适合作为默认研究频率。",
        "",
        "## 12. 下一步建议",
        "",
        "1. 把参数可视化从'找最优'改成'找稳定区域'。",
        "2. 固定比较 `Top2 2m`、`Top2 6m`、`Top2 9m`、`Top1 6m`，不要无限扩参数。",
        "3. 为每个候选参数补充：样本外年化、最大回撤、年化换手、成本拖累、纸面交易信号表现。",
        "4. 如果要画图，优先画：年化收益热力图、最大回撤热力图、样本外退化热力图、年化换手热力图。",
        "5. 决策时要求：收益不是孤峰，回撤可承受，样本外不崩，换手不过度。",
        "",
        "## 13. 关联数据文件",
        "",
        "- `outputs/etf_momentum_windows_topn_vectorbt_full_metrics.csv`",
        "- `outputs/etf_momentum_windows_topn_in_out_sample_summary.csv`",
        "- `outputs/etf_momentum_windows_topn_oos_ranking.csv`",
        "- `outputs/etf_momentum_rebalance_frequency_summary.csv`",
        "- `outputs/etf_momentum_rebalance_frequency_comparison_metrics.csv`",
        "- `outputs/etf_momentum_1to6_month_comparison_metrics.csv`",
        "- `outputs/sma_trend_parameter_scan.csv`",
    ]

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)
    print(CHECKLIST_PATH)


if __name__ == "__main__":
    main()
