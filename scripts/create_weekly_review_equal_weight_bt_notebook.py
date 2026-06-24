from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

BASE = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = BASE / "notebooks" / "weekly_review_equal_weight_bt_vectorbt.ipynb"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(text).strip().splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": dedent(text).strip().splitlines(keepends=True)}


cells = [
    md(
        """
        # 周复盘：bt 等权组合回测 Notebook

        本 Notebook 用项目已有脚本 `scripts/vectorbt_topn_etf_rotation.py` 复现 Top2/Top3 等权 ETF 轮动回测，并生成周复盘视角。

        定位：研究与纸面交易复盘，不是实盘建议。

        核心规则：

        - 数据：`data/etf_momentum_daily_eastmoney_qfq.csv`
        - 动量窗口：42 个交易日
        - 调仓频率：月度
        - Top2/Top3：选择动量为正的前 N 只行业/主题 ETF
        - 入选 ETF 等权持有
        - 若行业/主题 ETF 无正动量，则切到正动量防守资产；若防守资产也无正动量，则空仓
        - 成本：佣金 0.01%，滑点 0.01%
        """
    ),
    code(
        """
        from pathlib import Path
        import pandas as pd
        import numpy as np

        BASE = Path.cwd()
        if BASE.name == "notebooks":
            BASE = BASE.parent

        SCRIPT_PATH = BASE / "scripts" / "vectorbt_topn_etf_rotation.py"
        OUTPUT_DIR = BASE / "outputs"
        SCRIPT_PATH
        """
    ),
    md("""## 1. 重新执行等权组合回测

如果这里提示找不到 `vectorbt`，说明你没有用项目环境打开 Jupyter。请在 D:/Quant 目录运行：`uv run jupyter lab`，再打开本 Notebook。"""),
    code(
        """
        # 运行现有 vectorbt 回测脚本，刷新输出文件。
        try:
            import vectorbt as vbt
            print('vectorbt version:', vbt.__version__)
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError('当前 Notebook 内核没有 vectorbt。请在 D:/Quant 目录用 uv run jupyter lab 打开。') from exc

        %run $SCRIPT_PATH
        """
    ),
    md("""## 2. 读取汇总指标"""),
    code(
        """
        metrics = pd.read_csv(OUTPUT_DIR / "etf_topn_rotation_vectorbt_metrics.csv")
        metrics
        """
    ),
    md("""## 3. 格式化关键指标，方便周复盘阅读"""),
    code(
        """
        pct_cols = ["total_return", "annualized_return", "annualized_volatility", "max_drawdown", "fee_rate", "slippage"]
        view = metrics.copy()
        for col in pct_cols:
            if col in view.columns:
                view[col] = view[col].map(lambda x: f"{x:.2%}" if pd.notna(x) else "")
        for col in ["sharpe_like_no_rf", "annual_traded_value_ratio"]:
            if col in view.columns:
                view[col] = view[col].map(lambda x: f"{x:.2f}" if pd.notna(x) else "")
        view[["name", "top_n", "total_return", "annualized_return", "annualized_volatility", "max_drawdown", "sharpe_like_no_rf", "final_value", "order_count", "total_fees"]]
        """
    ),
    md("""## 4. 读取 Top2/Top3 最近调仓信号"""),
    code(
        """
        top2_decisions = pd.read_csv(OUTPUT_DIR / "etf_top2_equal_weight_rotation_vectorbt_decisions.csv", parse_dates=["signal_date"])
        top3_decisions = pd.read_csv(OUTPUT_DIR / "etf_top3_equal_weight_rotation_vectorbt_decisions.csv", parse_dates=["signal_date"])

        latest_signals = pd.concat([
            top2_decisions.tail(1).assign(strategy="Top2等权"),
            top3_decisions.tail(1).assign(strategy="Top3等权"),
        ], ignore_index=True)
        latest_signals[["strategy", "signal_date", "selected_symbols", "selected_names", "selected_bucket", "selected_count", "target_weight_each", "reason"]]
        """
    ),
    md("""## 5. 读取每日净值，计算最近 12 周周度表现"""),
    code(
        """
        def load_daily(top_n: int) -> pd.DataFrame:
            daily = pd.read_csv(OUTPUT_DIR / f"etf_top{top_n}_equal_weight_rotation_vectorbt_daily_value.csv", parse_dates=["date"])
            daily = daily.sort_values("date").set_index("date")
            daily["strategy"] = f"Top{top_n}等权"
            daily["weekly_return"] = daily["nav"].resample("W-FRI").last().pct_change()
            return daily

        top2_daily = load_daily(2)
        top3_daily = load_daily(3)

        weekly = pd.concat([
            top2_daily["nav"].resample("W-FRI").last().rename("Top2等权"),
            top3_daily["nav"].resample("W-FRI").last().rename("Top3等权"),
        ], axis=1).dropna()
        weekly_returns = weekly.pct_change().dropna()
        weekly_returns.tail(12)
        """
    ),
    md("""## 6. 最近 12 周复盘统计"""),
    code(
        """
        last_12w = weekly_returns.tail(12)
        review_stats = pd.DataFrame({
            "12周累计收益": (1 + last_12w).prod() - 1,
            "周胜率": (last_12w > 0).mean(),
            "最好单周": last_12w.max(),
            "最差单周": last_12w.min(),
            "周收益波动": last_12w.std(),
        }).T
        review_stats.map(lambda x: f"{x:.2%}")
        """
    ),
    md("""## 7. 画净值曲线"""),
    code(
        """
        ax = weekly.plot(figsize=(12, 5), title="Top2/Top3 等权 ETF 轮动净值曲线（周频）")
        ax.set_ylabel("NAV")
        ax.grid(True, alpha=0.3)
        """
    ),
    md("""## 8. 查看最近目标权重"""),
    code(
        """
        top2_weights = pd.read_csv(OUTPUT_DIR / "etf_top2_equal_weight_rotation_vectorbt_target_weights.csv", parse_dates=["date"])
        top3_weights = pd.read_csv(OUTPUT_DIR / "etf_top3_equal_weight_rotation_vectorbt_target_weights.csv", parse_dates=["date"])

        latest_top2_weights = top2_weights.tail(1).T
        latest_top2_weights.columns = ["Top2_latest_weight"]
        latest_top2_weights = latest_top2_weights[latest_top2_weights["Top2_latest_weight"].ne(0)]
        latest_top2_weights
        """
    ),
    code(
        """
        latest_top3_weights = top3_weights.tail(1).T
        latest_top3_weights.columns = ["Top3_latest_weight"]
        latest_top3_weights = latest_top3_weights[latest_top3_weights["Top3_latest_weight"].ne(0)]
        latest_top3_weights
        """
    ),
    md("""## 9. 查看最近订单"""),
    code(
        """
        top2_orders = pd.read_csv(OUTPUT_DIR / "etf_top2_equal_weight_rotation_vectorbt_orders.csv")
        top3_orders = pd.read_csv(OUTPUT_DIR / "etf_top3_equal_weight_rotation_vectorbt_orders.csv")

        top2_orders.tail(10)
        """
    ),
    code(
        """
        top3_orders.tail(10)
        """
    ),
    md(
        """
        ## 10. 周复盘结论模板

        填写时不要只看收益，至少回答：

        1. 本周 Top2/Top3 是否继续跑赢基准？
        2. 最近 12 周累计收益是否为正？
        3. 最差单周亏损是否在可承受范围内？
        4. 最新信号是否仍然集中在同一类资产？如果是，相关性风险是否过高？
        5. 是否出现频繁调仓、订单过多、成本明显抬升？
        6. 结论是继续观察、纸面交易强化，还是暂缓？
        """
    ),
    code(
        """
        conclusion_template = pd.DataFrame([
            ["本周结论", "继续观察 / 纸面交易强化 / 暂缓", ""],
            ["主要证据", "最近12周收益、回撤、信号集中度、订单和成本", ""],
            ["主要风险", "回撤、行业集中、规则失效、数据质量", ""],
            ["下周动作", "继续记录 / 检查异常 / 不改规则", ""],
        ], columns=["项目", "填写提示", "本周填写"])
        conclusion_template
        """
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
NOTEBOOK_PATH.write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")
print(NOTEBOOK_PATH)
