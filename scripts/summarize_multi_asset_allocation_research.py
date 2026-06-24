from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE / "outputs"
REPORT_PATH = OUTPUT_DIR / "multi_asset_allocation_research_summary.md"
TABLE_PATH = OUTPUT_DIR / "multi_asset_allocation_research_key_findings.csv"


def read_csv(name: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUT_DIR / name)


def pct(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.2%}"


def num(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.2f}"


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


def select_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return df[[column for column in columns if column in df.columns]].copy()


def build_key_findings() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "topic": "核心基准",
                "finding": "42日月度Top2等权明显跑赢510300买入持有，但最大回撤仍接近46%，不能称为低回撤策略。",
                "evidence_file": "bt_equal_weight_return_risk_evaluation_summary.csv / etf_topn_rotation_vectorbt_metrics.csv",
                "action": "继续研究Top2，但必须加入样本外、成本、纸面交易和风控观察。",
            },
            {
                "topic": "TopN差异",
                "finding": "Top2在收益和回撤之间优于Top3；Top3分散更多但收益下降，回撤改善不明显。",
                "evidence_file": "etf_topn_rotation_vectorbt_metrics.csv",
                "action": "优先把Top2作为候选基线，Top3作为保守对照，不急于扩到更多资产。",
            },
            {
                "topic": "窗口稳定性",
                "finding": "全样本最亮眼的短窗口在样本外退化明显；OOS排名显示Top1 6m、Top2 9m、Top2 2m值得继续比较。",
                "evidence_file": "etf_momentum_windows_topn_oos_ranking.csv",
                "action": "不要只用全样本最优参数；下一步做滚动/走前验证。",
            },
            {
                "topic": "调仓频率",
                "finding": "双周平均年化略高但换手更高；月度收益接近且操作负担更低；季度换手低但收益明显下降。",
                "evidence_file": "etf_momentum_rebalance_frequency_summary.csv",
                "action": "现阶段优先保留月度调仓，双周只作为对照，不直接进入纸面交易。",
            },
            {
                "topic": "成本压力",
                "finding": "基础成本影响较小，但在高成本和极端成本下年化收益明显下滑，说明策略对换手成本并非免疫。",
                "evidence_file": "etf_rotation_cost_stress_summary.csv",
                "action": "纸面交易记录真实成交价差，后续加入最小佣金和实际成交约束。",
            },
            {
                "topic": "未来函数与执行时序",
                "finding": "现有检查显示最近信号均能在下一交易日匹配目标权重，但存在同日权重非零现象，需要用'信号日收盘后、次日执行'口径解释。",
                "evidence_file": "bt_equal_weight_future_leakage_cost_check_summary.csv",
                "action": "继续在新脚本和报告中显式标注信号日、执行日、持仓生效日。",
            },
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    minimal = read_csv("bt_minimal_equal_weight_summary.csv")
    vectorbt_topn = read_csv("etf_topn_rotation_vectorbt_metrics.csv")
    risk_return = read_csv("bt_equal_weight_return_risk_evaluation_summary.csv")
    leakage = read_csv("bt_equal_weight_future_leakage_cost_check_summary.csv")
    cost_stress = read_csv("etf_rotation_cost_stress_summary.csv")
    oos_ranking = read_csv("etf_momentum_windows_topn_oos_ranking.csv")
    rebalance = read_csv("etf_momentum_rebalance_frequency_summary.csv")
    window_1to6 = read_csv("etf_momentum_1to6_month_comparison_metrics.csv")
    defensive = read_csv("etf_momentum_defensive_or_cash_metrics.csv")
    risk_filter = read_csv("etf_top1_top2_top3_risk_filter_42d_comparison.csv")

    key_findings = build_key_findings()
    key_findings.to_csv(TABLE_PATH, index=False, encoding="utf-8-sig")

    vectorbt_view = select_columns(
        vectorbt_topn,
        [
            "name",
            "top_n",
            "lookback_days",
            "rebalance_frequency",
            "total_return",
            "annualized_return",
            "annualized_volatility",
            "max_drawdown",
            "sharpe_like_no_rf",
            "order_count",
            "annual_traded_value_ratio",
            "cash_target_days",
        ],
    )
    risk_return_view = select_columns(
        risk_return,
        [
            "strategy",
            "total_return",
            "annualized_return",
            "annualized_volatility",
            "max_drawdown",
            "calmar",
            "excess_annualized_return_vs_510300",
            "drawdown_improvement_vs_510300",
        ],
    )
    oos_view = select_columns(
        oos_ranking.head(8),
        [
            "rank_oos_return",
            "strategy_name",
            "full_annualized_return",
            "is_annualized_return",
            "oos_annualized_return",
            "oos_max_drawdown",
            "annualized_return_oos_minus_is",
            "stability_flag",
        ],
    )
    rebalance_view = select_columns(
        rebalance,
        [
            "rebalance_frequency",
            "avg_annualized_return",
            "avg_max_drawdown",
            "avg_sharpe_like",
            "avg_annual_one_way_turnover",
            "avg_cost_drag",
        ],
    )
    cost_view = select_columns(
        cost_stress,
        [
            "scenario",
            "avg_annualized_return",
            "avg_max_drawdown",
            "avg_sharpe_like",
            "avg_cost_drag_vs_no_cost",
            "avg_annualized_drag_vs_no_cost",
        ],
    )
    leakage_view = select_columns(
        leakage,
        [
            "top_n",
            "checked_recent_signals",
            "next_day_match_count",
            "fee_rate",
            "slippage",
            "annual_traded_value_ratio",
            "total_return",
            "max_drawdown",
        ],
    )
    window_view = select_columns(
        window_1to6,
        [
            "window_label",
            "lookback_days",
            "annualized_return",
            "max_drawdown",
            "sharpe_like_no_rf",
            "trade_count",
            "cash_days",
            "defensive_days",
            "sector_days",
        ],
    )
    defensive_view = select_columns(
        defensive,
        [
            "name",
            "annualized_return",
            "annualized_volatility",
            "max_drawdown",
            "sharpe_like_no_rf",
            "trade_count",
            "cash_days",
            "defensive_days",
            "sector_days",
        ],
    )
    risk_filter_view = select_columns(
        risk_filter,
        [
            "version",
            "name",
            "top_n",
            "annualized_return",
            "annualized_volatility",
            "max_drawdown",
            "sharpe_like_no_rf",
            "annual_traded_value_ratio",
            "risk_on_signals",
            "defensive_signals",
            "cash_signals",
        ],
    )

    lines = [
        "# 多资产配置研究结果整理",
        "",
        "## 结论摘要",
        "",
        "这份报告整理的是本地 `D:/Quant` 项目已经跑出的 ETF 多资产/行业轮动研究结果，不是网络摘抄。当前研究对象主要是 A 股 ETF：行业/主题资产作为进攻池，防守资产作为风险回避池，沪深300 ETF 作为基准。",
        "",
        "核心结论：42日动量、月度调仓、Top2等权是目前最值得继续观察的候选基线；它明显跑赢 `510300` 买入持有，但最大回撤仍然很深，样本外也有退化迹象，所以只能进入更严格的纸面交易和稳健性验证，不能直接实盘。",
        "",
        "## 1. 研究问题",
        "",
        "本阶段要回答的问题不是'哪组参数收益最高'，而是：ETF 多资产/行业轮动是否比单一宽基买入持有更适合你的目标——控制回撤、慢慢复利、可解释、可复盘。",
        "",
        "## 2. 数据与策略口径",
        "",
        "- 数据源：`data/etf_momentum_daily_eastmoney_qfq.csv`，前复权 ETF 日线数据。",
        "- 资产分层：`sector` 参与排名，`defensive` 在行业资产无正动量时兜底，`benchmark` 只作基准对照。",
        "- 动量公式：`close / close.shift(lookback_days) - 1`。",
        "- 调仓时序：调仓日收盘后生成信号，下一交易日目标权重生效，避免同收盘价信号吃到同日收益。",
        "- 成本口径：ETF 不加股票印花税；基础口径为佣金 `0.01%` + 滑点 `0.01%` 单边成本。",
        "",
        "## 3. 关键发现",
        "",
        md_table(key_findings),
        "",
        "## 4. 42日月度TopN基线结果",
        "",
        "Top2 等权在收益、类夏普、回撤改善之间目前最均衡；Top3 分散度更高，但收益下降明显，回撤改善不足以补偿收益损失。Top1 全样本收益更高，但集中度更强，不能直接替代组合基线。",
        "",
        md_table(vectorbt_view),
        "",
        "## 5. 收益与风险评估",
        "",
        "Top2 相对 `510300` 有明显超额年化，但最大回撤仍约 `-46%`，这与'低回撤'目标还有距离。当前更准确的说法是：它改善了单一宽基持有的收益/回撤结构，但仍是高波动权益策略。",
        "",
        md_table(risk_return_view),
        "",
        "## 6. 最小bt实现的交叉验证",
        "",
        "最小 pandas 版 bt 与 vectorbt 版方向一致：Top2 优于 Top3 和买入持有。数值不完全相同，主要因为最小版按目标权重变化估算单边换手成本，而 vectorbt 记录逐资产订单与真实资金路径。最小版适合理解逻辑，vectorbt版更适合正式比较。",
        "",
        md_table(select_columns(minimal, ["name", "annualized_return", "annualized_volatility", "max_drawdown", "sharpe_like_no_rf", "trade_day_count", "annual_one_way_turnover", "total_cost_drag"])),
        "",
        "## 7. 样本内/样本外稳定性",
        "",
        "短窗口和高收益参数在样本外退化明显，这是最重要的风险信号。OOS 排名靠前的组合不一定是全样本最优：例如 Top1 6m、Top2 9m、Top2 2m 都值得比较，但 Top2 2m 标记为样本外明显退化，不能只看全样本收益。",
        "",
        md_table(oos_view),
        "",
        "## 8. 调仓频率与换手",
        "",
        "双周调仓平均年化略高，但换手和成本更高；月度调仓收益接近、执行负担更低；季度调仓虽然换手低，但收益下滑明显。对学习和纸面交易阶段，月度是更合理的默认频率。",
        "",
        md_table(rebalance_view),
        "",
        "## 9. 动量窗口与防守/空仓规则",
        "",
        "1到6个月窗口比较中，2个月和6个月表现较强，但3个月表现很差，说明窗口不是越长越好，也不是随便选都有效。防守/空仓规则确实改善了只强行持有行业ETF的问题，但不能消灭权益回撤。",
        "",
        md_table(window_view),
        "",
        md_table(defensive_view),
        "",
        "## 10. 成本压力与交易可行性",
        "",
        "基础成本下策略仍保持较好表现；但当单边成本升高时，平均年化收益递减、最大回撤变差。由于你的券商佣金是万1且有每笔5元最低佣金，小资金实盘时还必须额外检查最小佣金约束。",
        "",
        md_table(cost_view),
        "",
        "## 11. 未来函数与执行口径检查",
        "",
        "现有检查显示最近信号的次日目标权重匹配数等于检查信号数，说明核心执行口径是可解释的。但同日已有权重不一定是错误：它可能来自上一次信号延续持仓。报告和脚本必须持续区分信号日、执行日和持仓日。",
        "",
        md_table(leakage_view),
        "",
        "## 12. 风险过滤实验",
        "",
        "当前风险过滤版本和原始版本指标一致，说明新增过滤条件没有真正改变基线策略，或者过滤条件与原策略已有的正动量/防守/空仓逻辑重叠。下一步如果继续做风控，应加入真正独立的条件，例如宽基趋势过滤、组合回撤止损、波动目标或资产相关性约束。",
        "",
        md_table(risk_filter_view),
        "",
        "## 13. 当前可写入策略日志的结论",
        "",
        "- 候选基线：`Top2 + 42日动量 + 月度调仓 + 正动量筛选 + 防守/空仓兜底`。",
        "- 当前证据：全样本和正式 vectorbt 结果显示显著跑赢 `510300`，但最大回撤仍接近 `-46%`。",
        "- 主要优点：规则简单、可解释、能输出明确月度信号、比单一宽基更有进攻性。",
        "- 主要问题：样本外退化、回撤仍深、换手和成本需要实盘化估计、Top1/Top2/Top3和窗口选择存在参数挖掘风险。",
        "- 当前判断：支持继续研究和纸面交易观察，不支持直接实盘放大资金。",
        "",
        "## 14. 下一步行动",
        "",
        "1. 固定一个候选版本做12周纸面交易，不再频繁改参数。",
        "2. 同步记录每次信号、理论成交价、实际可成交价、滑点、最低佣金影响。",
        "3. 对 Top2 42日、Top2 9月、Top1 6月 做滚动样本外或走前比较。",
        "4. 加入宽基趋势过滤或波动目标，但必须证明它和现有防守/空仓规则不同。",
        "5. 用小资金前，先把最低5元佣金和单笔成交金额阈值纳入成本模型。",
        "",
        "## 15. 关联产物",
        "",
        "- 最小bt报告：`outputs/bt_minimal_equal_weight_report.md`。",
        "- vectorbt TopN报告：`outputs/etf_topn_rotation_vectorbt_report.md`。",
        "- 收益风险评估：`outputs/bt_equal_weight_return_risk_evaluation.md`。",
        "- 样本内外稳定性：`outputs/etf_momentum_windows_topn_in_out_sample_report.md`。",
        "- 成本压力测试：`outputs/etf_rotation_cost_stress_report.md`。",
        "- 未来函数与成本检查：`outputs/bt_equal_weight_future_leakage_cost_check.md`。",
    ]

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)
    print(TABLE_PATH)


if __name__ == "__main__":
    main()
