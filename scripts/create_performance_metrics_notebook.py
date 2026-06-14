import json
from pathlib import Path
from textwrap import dedent

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "08_performance_metrics_explained.ipynb"


def md(source: str) -> dict:
    clean_source = dedent(source).strip()
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [line + "\n" for line in clean_source.splitlines()],
    }


def code(source: str) -> dict:
    clean_source = dedent(source).strip()
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [line + "\n" for line in clean_source.splitlines()],
    }


cells = [
    md(
        """
        # 08｜理解回测绩效指标：收益、年化、波动、回撤、夏普

        这一节不是评估真实策略，而是用一组**手工可检查的小样本数据**理解绩效指标。

        你要完成的目标：

        1. 知道 `returns` 和 `equity` 分别是什么。
        2. 能解释总收益率、CAGR、年化波动率、最大回撤、Sharpe Ratio。
        3. 会调用 `scripts/performance_metrics.py` 生成统一指标表。
        4. 明白这些指标什么时候会误导你。

        > 学习提醒：指标不是用来证明策略好，而是用来逼你更冷静地看风险和收益。
        """
    ),
    md(
        """
        ## 1. 先区分两个输入：returns 与 equity

        在回测里最常见的两条序列是：

        ```text
        returns[t] = 本周期收益率
        equity[t] = 从初始资金复利滚出来的净值曲线
        ```

        例如某策略连续 4 天收益是：

        ```text
        +1%, -2%, +3%, 0%
        ```

        如果初始净值是 `1.0`，那么净值曲线不是简单相加，而是复利相乘：

        ```text
        第1天：1.0 * (1 + 0.01)
        第2天：1.0 * (1 + 0.01) * (1 - 0.02)
        第3天：继续乘 (1 + 0.03)
        ```
        """
    ),
    code(
        """
        from pathlib import Path
        import sys

        import numpy as np
        import pandas as pd

        project_root = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
        if str(project_root) not in sys.path:
            sys.path.append(str(project_root))

        from scripts.performance_metrics import (
            annualized_volatility,
            cagr,
            drawdown_curve,
            equity_curve_from_returns,
            format_performance_summary,
            max_drawdown,
            performance_summary,
            sharpe_ratio,
            total_return,
        )
        """
    ),
    code(
        """
        returns = pd.Series(
            [0.01, -0.02, 0.03, 0.00, -0.04, 0.02],
            index=pd.to_datetime([
                "2026-01-01",
                "2026-01-02",
                "2026-01-03",
                "2026-01-04",
                "2026-01-05",
                "2026-01-06",
            ]),
            name="strategy_ret",
        )

        equity = equity_curve_from_returns(returns)

        df = pd.DataFrame({
            "return": returns,
            "equity": equity,
        })

        df
        """
    ),
    md(
        """
        ## 2. 总收益率 total_return

        总收益率回答的是：**从开始到结束，一共赚/亏了多少比例？**

        公式：

        ```text
        total_return = 期末净值 / 期初净值 - 1
        ```

        注意：它不关心中间过程。两个策略总收益一样，风险可能完全不同。
        """
    ),
    code(
        """
        manual_total_return = equity.iloc[-1] / equity.iloc[0] - 1
        module_total_return = total_return(equity)

        print(f"手算总收益率: {manual_total_return:.4%}")
        print(f"模块总收益率: {module_total_return:.4%}")
        """
    ),
    md(
        """
        ## 3. CAGR：复合年化收益率

        CAGR 回答的是：**如果这段收益按复利折算成一年，大约是多少年化增长率？**

        在日频回测中常用 `periods_per_year=252`，因为一年大约有 252 个交易日。

        公式思想：

        ```text
        cagr = 期末净值 ** (一年周期数 / 样本周期数) - 1
        ```

        重要提醒：样本很短时，CAGR 会被严重放大，不要过度解读。
        """
    ),
    code(
        """
        periods_per_year = 252
        manual_cagr = equity.iloc[-1] ** (periods_per_year / len(equity)) - 1
        module_cagr = cagr(equity, periods_per_year=periods_per_year)

        print(f"手算 CAGR: {manual_cagr:.4%}")
        print(f"模块 CAGR: {module_cagr:.4%}")
        """
    ),
    md(
        """
        ## 4. 年化波动率 annual_vol

        年化波动率回答的是：**收益率上下波动有多剧烈？**

        它不是对价格算标准差，而是对周期收益率算标准差：

        ```text
        annual_vol = std(returns, ddof=1) * sqrt(periods_per_year)
        ```

        这里 `ddof=1` 表示样本标准差，常用于历史样本估计。
        """
    ),
    code(
        """
        manual_vol = returns.std(ddof=1) * np.sqrt(periods_per_year)
        module_vol = annualized_volatility(returns, periods_per_year=periods_per_year)

        print(f"手算年化波动率: {manual_vol:.4%}")
        print(f"模块年化波动率: {module_vol:.4%}")
        """
    ),
    md(
        """
        ## 5. 回撤曲线与最大回撤

        回撤回答的是：**从历史最高点跌下来多少？**

        每一天的回撤：

        ```text
        drawdown[t] = 当前净值 / 截至当前的历史最高净值 - 1
        ```

        最大回撤就是整条回撤曲线里最小的那个值。

        这对你的目标很重要：你追求的是回撤控制和慢复利，不是只看收益率。
        """
    ),
    code(
        """
        df["running_peak"] = df["equity"].cummax()
        df["drawdown"] = drawdown_curve(df["equity"])

        display(df)
        print(f"最大回撤: {max_drawdown(df['equity']):.4%}")
        """
    ),
    md(
        """
        ## 6. Sharpe Ratio：单位波动换来的收益

        Sharpe Ratio 回答的是：**每承担一份波动，大约换来多少超额收益？**

        简化版，不考虑无风险利率：

        ```text
        sharpe = mean(returns) / std(returns, ddof=1) * sqrt(periods_per_year)
        ```

        更完整版本会先扣除无风险利率：

        ```text
        period_rf = (1 + annual_risk_free_rate) ** (1 / periods_per_year) - 1
        excess_returns = returns - period_rf
        sharpe = mean(excess_returns) / std(excess_returns, ddof=1) * sqrt(periods_per_year)
        ```

        注意：Sharpe 假设波动能代表风险，但它不一定能充分描述尾部风险、流动性风险和极端回撤。
        """
    ),
    code(
        """
        manual_sharpe_no_rf = returns.mean() / returns.std(ddof=1) * np.sqrt(periods_per_year)
        module_sharpe_no_rf = sharpe_ratio(returns, periods_per_year=periods_per_year)
        module_sharpe_with_rf = sharpe_ratio(
            returns,
            periods_per_year=periods_per_year,
            annual_risk_free_rate=0.02,
        )

        print(f"手算 Sharpe（不扣无风险利率）: {manual_sharpe_no_rf:.4f}")
        print(f"模块 Sharpe（不扣无风险利率）: {module_sharpe_no_rf:.4f}")
        print(f"模块 Sharpe（扣 2% 年化无风险利率）: {module_sharpe_with_rf:.4f}")
        """
    ),
    md(
        """
        ## 7. 一次性生成绩效汇总表

        真实 Notebook 里不建议每次手写一遍公式。你应该把策略收益率和净值曲线交给模块统一计算。

        这样做有三个好处：

        1. 口径一致，不会今天一种公式、明天一种公式。
        2. 更容易测试，避免手滑写错。
        3. 后面比较策略和基准时，表格结构稳定。
        """
    ),
    code(
        """
        summary = pd.DataFrame(
            {
                "example_strategy": performance_summary(
                    returns,
                    equity=equity,
                    periods_per_year=periods_per_year,
                    annual_risk_free_rate=0.0,
                )
            }
        ).T

        summary
        """
    ),
    code(
        """
        format_performance_summary(summary)
        """
    ),
    md(
        """
        ## 8. 和一个基准做对比

        评价策略不能只看自己。至少要和一个基准比较。

        下面构造一个示例基准，不代表真实市场，只用于理解表格比较方式。
        """
    ),
    code(
        """
        benchmark_returns = pd.Series(
            [0.005, -0.015, 0.02, 0.01, -0.03, 0.015],
            index=returns.index,
            name="benchmark_ret",
        )
        benchmark_equity = equity_curve_from_returns(benchmark_returns)

        comparison = pd.DataFrame(
            {
                "example_strategy": performance_summary(
                    returns,
                    equity=equity,
                    periods_per_year=periods_per_year,
                ),
                "example_benchmark": performance_summary(
                    benchmark_returns,
                    equity=benchmark_equity,
                    periods_per_year=periods_per_year,
                ),
            }
        ).T

        format_performance_summary(comparison)
        """
    ),
    md(
        """
        ## 9. 怎么写周复盘

        这周如果还没有真实策略，复盘不要写“评估 Week05 策略”。更准确的写法是：

        ```text
        本周我用示例收益率和净值数据理解了绩效指标，并确认 performance_metrics.py 可以统一计算指标表。
        ```

        可以回答这几个问题：

        1. `returns` 和 `equity` 的区别是什么？
        2. 总收益率和 CAGR 为什么不是一回事？
        3. 年化波动率为什么要对收益率算标准差？
        4. 最大回撤为什么对实盘心理压力很重要？
        5. Sharpe 高是否一定代表策略好？为什么不一定？
        6. 等以后有真实策略时，我会如何比较策略和基准？
        """
    ),
    md(
        """
        ## 10. 本节边界

        当前 Notebook 只用于理解指标，不代表完整回测评价。

        未来评估真实策略时，还需要继续检查：

        - 手续费和滑点；
        - 信号和持仓是否 `shift(1)`，有没有偷看未来；
        - 是否和合理基准比较；
        - 样本内/样本外是否分开；
        - 参数是否稳健；
        - 收益是否集中来自少数极端日期。
        """
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.11",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
NOTEBOOK_PATH.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(NOTEBOOK_PATH)
