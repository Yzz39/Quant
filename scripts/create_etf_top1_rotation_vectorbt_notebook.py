from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

BASE = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = BASE / "notebooks" / "etf_top1_rotation_vectorbt.ipynb"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(text).strip().splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": dedent(text).strip().splitlines(keepends=True)}


cells = [
    md(
        """
        # vectorbt 实现 Top1 ETF 轮动

        本 notebook 调用项目脚本 `scripts/vectorbt_top1_etf_rotation.py`，用 vectorbt 执行 Top1 ETF 轮动回测。

        规则：

        - 行业/主题 ETF 中按过去 `42` 个交易日动量排序；
        - 每月末生成信号，下一交易日目标权重生效；
        - 若 Top1 行业 ETF 动量为正，满仓持有；
        - 若 Top1 行业 ETF 动量为负或不可用，切到正动量防守资产；
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

        SCRIPT_PATH = BASE / "scripts" / "vectorbt_top1_etf_rotation.py"
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
    md("""## 2. 读取指标与最新信号"""),
    code(
        """
        metrics_path = BASE / "outputs" / "etf_top1_rotation_vectorbt_metrics.csv"
        decisions_path = BASE / "outputs" / "etf_top1_rotation_vectorbt_decisions.csv"
        orders_path = BASE / "outputs" / "etf_top1_rotation_vectorbt_orders.csv"
        daily_path = BASE / "outputs" / "etf_top1_rotation_vectorbt_daily_value.csv"

        metrics = pd.read_csv(metrics_path)
        decisions = pd.read_csv(decisions_path, parse_dates=["signal_date"])
        orders = pd.read_csv(orders_path)
        daily = pd.read_csv(daily_path, parse_dates=["date"])

        metrics
        """
    ),
    code(
        """
        decisions.tail(10)
        """
    ),
    md("""## 3. 查看 vectorbt 订单"""),
    code(
        """
        orders.head(20)
        """
    ),
    code(
        """
        orders.tail(20)
        """
    ),
    md("""## 4. 查看净值曲线数据"""),
    code(
        """
        daily.tail()
        """
    ),
    md(
        """
        ## 5. 输出文件

        - 每日净值：`outputs/etf_top1_rotation_vectorbt_daily_value.csv`
        - 目标权重：`outputs/etf_top1_rotation_vectorbt_target_weights.csv`
        - 调仓决策：`outputs/etf_top1_rotation_vectorbt_decisions.csv`
        - vectorbt 订单：`outputs/etf_top1_rotation_vectorbt_orders.csv`
        - 回测指标：`outputs/etf_top1_rotation_vectorbt_metrics.csv`
        - Markdown 报告：`outputs/etf_top1_rotation_vectorbt_report.md`
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
