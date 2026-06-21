from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

BASE = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = BASE / "notebooks" / "etf_top2_top3_equal_weight_rotation_vectorbt.ipynb"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(text).strip().splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": dedent(text).strip().splitlines(keepends=True)}


cells = [
    md(
        """
        # vectorbt 实现 Top2/Top3 等权 ETF 轮动

        本 notebook 调用项目脚本 `scripts/vectorbt_topn_etf_rotation.py`，用 vectorbt 执行 Top2 与 Top3 等权 ETF 轮动回测。

        规则：

        - 行业/主题 ETF 中按过去 `42` 个交易日动量排序；
        - 每月末生成信号，下一交易日目标权重生效；
        - Top2：选择动量为正的前 2 只 ETF，等权持有；
        - Top3：选择动量为正的前 3 只 ETF，等权持有；
        - 若正动量标的不足 N 只，则只持有实际入选标的并等权；
        - 若行业/主题 ETF 全部无正动量，切到正动量防守资产；
        - 若防守资产也无正动量，则空仓；
        - vectorbt 成本：佣金 `0.01%`，滑点 `0.01%`。
        """
    ),
    code(
        """
        from pathlib import Path
        import pandas as pd

        BASE = Path.cwd()
        if BASE.name == "notebooks":
            BASE = BASE.parent

        SCRIPT_PATH = BASE / "scripts" / "vectorbt_topn_etf_rotation.py"
        SCRIPT_PATH
        """
    ),
    md("""## 1. 执行回测脚本"""),
    code(
        """
        # 在 notebook 里直接执行脚本，重新生成输出文件。
        %run $SCRIPT_PATH
        """
    ),
    md("""## 2. 读取 Top2/Top3 汇总指标"""),
    code(
        """
        summary_metrics_path = BASE / "outputs" / "etf_topn_rotation_vectorbt_metrics.csv"
        summary_metrics = pd.read_csv(summary_metrics_path)
        summary_metrics
        """
    ),
    md("""## 3. 查看调仓决策"""),
    code(
        """
        top2_decisions = pd.read_csv(
            BASE / "outputs" / "etf_top2_equal_weight_rotation_vectorbt_decisions.csv",
            parse_dates=["signal_date"],
        )
        top3_decisions = pd.read_csv(
            BASE / "outputs" / "etf_top3_equal_weight_rotation_vectorbt_decisions.csv",
            parse_dates=["signal_date"],
        )

        top2_decisions.tail(10)
        """
    ),
    code(
        """
        top3_decisions.tail(10)
        """
    ),
    md("""## 4. 查看目标权重"""),
    code(
        """
        top2_weights = pd.read_csv(BASE / "outputs" / "etf_top2_equal_weight_rotation_vectorbt_target_weights.csv", parse_dates=["date"])
        top3_weights = pd.read_csv(BASE / "outputs" / "etf_top3_equal_weight_rotation_vectorbt_target_weights.csv", parse_dates=["date"])

        top2_weights.tail()
        """
    ),
    code(
        """
        top3_weights.tail()
        """
    ),
    md("""## 5. 查看 vectorbt 订单"""),
    code(
        """
        top2_orders = pd.read_csv(BASE / "outputs" / "etf_top2_equal_weight_rotation_vectorbt_orders.csv")
        top3_orders = pd.read_csv(BASE / "outputs" / "etf_top3_equal_weight_rotation_vectorbt_orders.csv")

        top2_orders.tail(20)
        """
    ),
    code(
        """
        top3_orders.tail(20)
        """
    ),
    md("""## 6. 查看净值曲线数据"""),
    code(
        """
        top2_daily = pd.read_csv(BASE / "outputs" / "etf_top2_equal_weight_rotation_vectorbt_daily_value.csv", parse_dates=["date"])
        top3_daily = pd.read_csv(BASE / "outputs" / "etf_top3_equal_weight_rotation_vectorbt_daily_value.csv", parse_dates=["date"])

        top2_daily.tail()
        """
    ),
    code(
        """
        top3_daily.tail()
        """
    ),
    md(
        """
        ## 7. 输出文件

        - 汇总指标：`outputs/etf_topn_rotation_vectorbt_metrics.csv`
        - Markdown 报告：`outputs/etf_topn_rotation_vectorbt_report.md`
        - Top2 每日净值：`outputs/etf_top2_equal_weight_rotation_vectorbt_daily_value.csv`
        - Top2 目标权重：`outputs/etf_top2_equal_weight_rotation_vectorbt_target_weights.csv`
        - Top2 调仓决策：`outputs/etf_top2_equal_weight_rotation_vectorbt_decisions.csv`
        - Top2 vectorbt 订单：`outputs/etf_top2_equal_weight_rotation_vectorbt_orders.csv`
        - Top2 回测指标：`outputs/etf_top2_equal_weight_rotation_vectorbt_metrics.csv`
        - Top3 每日净值：`outputs/etf_top3_equal_weight_rotation_vectorbt_daily_value.csv`
        - Top3 目标权重：`outputs/etf_top3_equal_weight_rotation_vectorbt_target_weights.csv`
        - Top3 调仓决策：`outputs/etf_top3_equal_weight_rotation_vectorbt_decisions.csv`
        - Top3 vectorbt 订单：`outputs/etf_top3_equal_weight_rotation_vectorbt_orders.csv`
        - Top3 回测指标：`outputs/etf_top3_equal_weight_rotation_vectorbt_metrics.csv`
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
