"""Reusable performance metric helpers for Quant backtests.

本模块提供回测绩效分析中最常用的一组小工具：

- 把周期收益率 ``returns`` 复利成净值曲线 ``equity``。
- 计算总收益、年化收益率、年化波动率、最大回撤和夏普比率。
- 把结果整理成适合 Jupyter Notebook 展示的表格。

核心输入约定
------------
``returns`` 是每个周期的收益率，例如日频收益率 ``0.01`` 表示当天 +1%。
``equity`` 是净值/资金曲线，通常从 ``1.0`` 或 ``100.0`` 开始，所有值必须大于 0。
``periods_per_year`` 是一年有多少个周期：日频常用 252，周频常用 52，月频常用 12。

在 ipynb 中的典型用法
--------------------
假设 notebook 已经有一个 DataFrame ``df``，其中：

- ``df["strategy_ret"]`` 是策略日收益率。
- ``df["benchmark_ret"]`` 是基准日收益率。

可以这样生成绩效对比表：

.. code-block:: python

    import pandas as pd

    from scripts.performance_metrics import (
        equity_curve_from_returns,
        performance_summary,
        format_performance_summary,
        drawdown_curve,
    )

    # 1. 先由每日收益率生成净值曲线
    df["strategy_equity"] = equity_curve_from_returns(df["strategy_ret"])
    df["benchmark_equity"] = equity_curve_from_returns(df["benchmark_ret"])

    # 2. 分别计算策略和基准的绩效指标
    summary = pd.DataFrame(
        {
            "strategy": performance_summary(
                df["strategy_ret"],
                equity=df["strategy_equity"],
                periods_per_year=252,
                annual_risk_free_rate=0.02,  # 可选：年化无风险利率，例如 2%
            ),
            "benchmark": performance_summary(
                df["benchmark_ret"],
                equity=df["benchmark_equity"],
                periods_per_year=252,
            ),
        }
    ).T

    # 3. 在 notebook 中展示百分比格式后的表格
    format_performance_summary(summary)

    # 4. 如需画回撤曲线
    df["strategy_drawdown"] = drawdown_curve(df["strategy_equity"])
    df["strategy_drawdown"].plot(title="Strategy drawdown")

如果 notebook 不在项目根目录启动，导入 ``scripts.performance_metrics`` 可能失败。
这种情况下先把项目根目录加入 ``sys.path``：

.. code-block:: python

    import sys
    from pathlib import Path

    project_root = Path.cwd().parent  # 例如当前在 notebooks/ 目录
    sys.path.append(str(project_root))
"""

from __future__ import annotations
# 语法备注：
# ``from __future__ import annotations`` 会延迟解析类型标注。
# 好处是下面这些 ``pd.Series | Iterable[float]``、``dict[str, float]``
# 主要作为“给人和编辑器看的说明”，不会在函数定义时立刻求值。

from collections.abc import Iterable
import math

import numpy as np
import pandas as pd
# 语法备注：
# ``import numpy as np`` 和 ``import pandas as pd`` 是别名导入。
# 后面用 ``np.nan``、``pd.Series``，等价于写 ``numpy.nan``、``pandas.Series``，
# 只是量化/Python 数据分析里大家通常都用 np、pd 这两个简写。


def _to_numeric_series(values: pd.Series | Iterable[float], *, name: str) -> pd.Series:
    """Convert an iterable into a numeric pandas Series and drop missing values.

    这个内部函数负责统一清洗输入：无论传入的是 pandas Series、list，
    还是其他可迭代对象，最终都转换成数值型 Series。无法转换为数字的值
    会变成 NaN 并被移除。
    """
    # 语法备注：
    # ``values: pd.Series | Iterable[float]`` 是类型标注，意思是 values 可以是：
    # 1. pandas Series；或者
    # 2. 一个能逐个取出 float 的可迭代对象，例如 list、tuple、生成器。
    #
    # ``*, name: str`` 里的单独星号表示：星号后面的参数必须用关键字传入。
    # 所以调用时要写 ``_to_numeric_series(data, name="returns")``，
    # 不能写 ``_to_numeric_series(data, "returns")``。
    #
    # ``-> pd.Series`` 表示这个函数预期返回一个 pandas Series。
    if isinstance(values, pd.Series):
        # 语法备注：
        # ``isinstance(values, pd.Series)`` 用来判断 values 是不是 Series 类型。
        # copy() 避免后续清洗过程意外修改调用方传入的原始 Series。
        series = values.copy()
    else:
        # list(values) 可以兼容生成器等一次性迭代对象。
        series = pd.Series(list(values))

    series = pd.to_numeric(series, errors="coerce").dropna()
    # 语法备注：
    # 这一行是“链式调用”：先执行 pd.to_numeric(...)，得到 Series 后，
    # 立刻继续执行 ``.dropna()`` 删除缺失值。
    #
    # ``errors="coerce"`` 是关键字参数，表示转换失败时不要报错，
    # 而是把失败的值变成 NaN。
    if series.empty:
        # 语法备注：
        # ``f"{name} ..."`` 是 f-string，可以把变量 name 的值插进字符串里。
        raise ValueError(f"{name} must contain at least one non-missing value")
        # 语法备注：
        # ``raise ValueError(...)`` 表示主动抛出异常，让调用方知道输入不合法。

    return series


def _to_returns_series(returns: pd.Series | Iterable[float]) -> pd.Series:
    """Normalize a periodic return series for metric calculations."""
    return _to_numeric_series(returns, name="returns")


def _to_equity_series(equity: pd.Series | Iterable[float]) -> pd.Series:
    """Convert an equity curve to a numeric Series and validate it.

    净值/资金曲线不能小于等于 0，因为总收益、复利年化和回撤计算都依赖
    正数净值。如果出现 0 或负数，通常意味着数据或回测记账逻辑需要先检查。
    """
    if isinstance(equity, pd.Series):
        series = equity.copy()
    else:
        series = pd.Series(list(equity))

    # 这里不立刻 dropna，是为了让 drawdown_curve 保留原始索引上的缺失位置。
    series = pd.to_numeric(series, errors="coerce")
    valid = series.dropna()
    if valid.empty:
        raise ValueError("equity must contain at least one non-missing value")
    if (valid <= 0).any():
        # 语法备注：
        # ``valid <= 0`` 会对 Series 里的每个元素做比较，得到一串 True/False。
        # ``.any()`` 表示只要其中有一个 True，整个条件就成立。
        raise ValueError("equity values must be positive")
    return series


def annualized_volatility(
    returns: pd.Series | Iterable[float],
    periods_per_year: int = 252,
) -> float:
    """Return annualized volatility from periodic returns.

    Uses sample standard deviation (``ddof=1``), which is the common choice when
    estimating volatility from historical return samples.

    年化波动率 = 周期收益率样本标准差 * sqrt(一年周期数)。

    Example
    -------
    .. code-block:: python

        annualized_volatility(df["strategy_ret"], periods_per_year=252)
    """
    # 语法备注：
    # 函数参数里的 ``periods_per_year: int = 252`` 同时做了两件事：
    # 1. ``: int`` 说明它最好是整数；
    # 2. ``= 252`` 给了默认值，所以调用时可以不传这个参数。
    series = _to_returns_series(returns)
    if len(series) < 2:
        # 少于两个样本无法计算样本标准差，因此返回 NaN。
        return np.nan
    return float(series.std(ddof=1) * math.sqrt(periods_per_year))
    # 语法备注：
    # ``float(...)`` 把 numpy/pandas 计算出来的数值转成 Python 原生 float，
    # 这样函数返回值更简单，也更适合放进普通 dict 或打印展示。


def sharpe_ratio(
    returns: pd.Series | Iterable[float],
    periods_per_year: int = 252,
    annual_risk_free_rate: float = 0.0,
) -> float:
    """Return annualized Sharpe ratio from periodic returns.

    Sharpe = mean(period_return - period_risk_free_rate)
             / std(period_return - period_risk_free_rate)
             * sqrt(periods_per_year)

    ``annual_risk_free_rate`` is converted into a per-period rate by compound
    de-annualization before subtracting it from each period return.

    注意：这里假设 ``returns`` 的频率和 ``periods_per_year`` 匹配。例如日频收益率
    搭配 252，月频收益率搭配 12。
    """
    series = _to_returns_series(returns)
    if len(series) < 2:
        return np.nan

    # 把年化无风险利率折算成单周期利率，再从每期收益率中扣除。
    period_risk_free_rate = (1.0 + annual_risk_free_rate) ** (1.0 / periods_per_year) - 1.0
    # 语法备注：
    # ``**`` 是乘方运算符，例如 ``2 ** 3`` 等于 8。
    # 这里的 ``1.0 / periods_per_year`` 是年化到单周期的指数。
    excess_returns = series - period_risk_free_rate
    # 语法备注：
    # pandas Series 可以直接减去一个数字，pandas 会把这个数字应用到每一行。
    volatility = excess_returns.std(ddof=1)
    if volatility == 0 or np.isnan(volatility):
        # 语法备注：
        # ``or`` 是逻辑“或”：两个条件只要有一个为 True，就进入这个 if。
        return np.nan

    return float(excess_returns.mean() / volatility * math.sqrt(periods_per_year))


def drawdown_curve(equity: pd.Series | Iterable[float]) -> pd.Series:
    """Return the drawdown curve of an equity/net-value series.

    Drawdown is calculated as current_equity / historical_running_peak - 1.
    New highs are therefore 0; values below the previous high are negative.
    Missing values are preserved as missing values and ignored by the running
    peak calculation, matching pandas ``cummax`` behavior.

    回撤曲线的取值通常小于等于 0。例如 -0.20 表示从历史高点回撤 20%。
    """
    series = _to_equity_series(equity)
    # cummax() 记录每个时点之前出现过的最高净值，即“历史峰值”。
    running_peak = series.cummax()
    result = series / running_peak - 1.0
    result.name = "drawdown"
    return result


def max_drawdown(equity: pd.Series | Iterable[float]) -> float:
    """Return the maximum drawdown as the worst negative value in the curve.

    返回值越负，历史最大亏损坑越深。例如 -0.35 表示最大回撤为 -35%。
    """
    return float(drawdown_curve(equity).min())


def equity_curve_from_returns(
    returns: pd.Series | Iterable[float],
    *,
    initial_equity: float = 1.0,
) -> pd.Series:
    """Build an equity curve from periodic returns.

    Missing returns are treated as 0-period returns so the curve remains aligned
    with the original index.

    例如 ``returns = [0.10, -0.05]`` 且 ``initial_equity=1.0`` 时：
    第一期净值为 ``1.0 * (1 + 0.10) = 1.10``，
    第二期净值为 ``1.10 * (1 - 0.05) = 1.045``。
    """
    # 语法备注：
    # 函数参数列表中单独的 ``*`` 表示：
    # ``initial_equity`` 必须写成关键字参数。
    # 正确：``equity_curve_from_returns(returns, initial_equity=100.0)``
    # 错误：``equity_curve_from_returns(returns, 100.0)``
    if initial_equity <= 0:
        raise ValueError("initial_equity must be positive")

    if isinstance(returns, pd.Series):
        series = returns.copy()
    else:
        series = pd.Series(list(returns))

    # 缺失收益率按 0 处理，可以避免净值曲线因为个别缺失值断掉。
    numeric_returns = pd.to_numeric(series, errors="coerce").fillna(0.0)
    equity = initial_equity * (1.0 + numeric_returns).cumprod()
    # 语法备注：
    # ``.cumprod()`` 是 cumulative product，累计连乘。
    # 对收益率来说，就是把每一期 ``1 + return`` 一路复利乘起来。
    equity.name = "equity"
    return equity


def total_return(equity: pd.Series | Iterable[float]) -> float:
    """Return total return from an equity curve.

    总收益 = 最后一期净值 / 第一期净值 - 1。
    如果净值从 1.0 到 1.25，总收益就是 25%。
    """
    series = _to_equity_series(equity)
    first = float(series.iloc[0])
    last = float(series.iloc[-1])
    return last / first - 1.0


def cagr(
    equity: pd.Series | Iterable[float],
    periods_per_year: int = 252,
) -> float:
    """Return compound annual growth rate from an equity curve.

    当前实现沿用本项目 notebook 的净值约定：净值曲线通常从 1.0 起步，
    并且传入的每个点代表一个已完成的收益周期。因此计算公式使用
    ``ending_equity ** (periods_per_year / number_of_periods) - 1``。

    如果你传入的是从 100 起步的资金曲线，或者想按“首尾净值比”计算 CAGR，
    需要先把资金曲线归一化，例如 ``equity / equity.iloc[0]``。
    """
    series = _to_equity_series(equity)
    periods = len(series)
    if periods < 2:
        return np.nan
    return float(series.iloc[-1] ** (periods_per_year / periods) - 1.0)
    # 语法备注：
    # ``series.iloc[-1]`` 表示按位置取最后一个元素。
    # 在 Python 中，索引 ``-1`` 通常代表“最后一个”。


def performance_summary(
    returns: pd.Series | Iterable[float],
    equity: pd.Series | Iterable[float] | None = None,
    periods_per_year: int = 252,
    annual_risk_free_rate: float = 0.0,
) -> dict[str, float]:
    """Summarize a strategy using the standard backtest metrics in this repo.

    Parameters
    ----------
    returns:
        周期收益率序列，例如策略的日收益率。
    equity:
        可选的净值曲线。如果不传入，本函数会自动用 ``returns`` 生成。
    periods_per_year:
        年化时使用的一年周期数，日频通常为 252。
    annual_risk_free_rate:
        年化无风险利率，用于计算夏普比率，默认 0。

    Returns
    -------
    dict[str, float]
        包含 ``total_return``、``cagr``、``annual_vol``、``max_drawdown``、
        ``sharpe_ratio`` 五个指标。
    """
    # 语法备注：
    # ``equity: pd.Series | Iterable[float] | None = None`` 的意思是：
    # equity 可以是 Series、可迭代数字对象，或者 None。
    # ``None`` 表示“没有传入净值曲线”，函数会自己从 returns 生成。
    #
    # ``-> dict[str, float]`` 表示函数返回一个字典：
    # key 是字符串，value 是浮点数。
    returns_series = _to_returns_series(returns)
    if equity is None:
        # 语法备注：
        # 判断一个变量是不是 None，推荐写 ``is None``，而不是 ``== None``。
        # 没有传入净值时，默认从收益率复利生成一条初始净值为 1.0 的曲线。
        equity_series = equity_curve_from_returns(returns_series)
    else:
        equity_series = _to_equity_series(equity)

    return {
        # 语法备注：
        # 这里返回的是 dict 字典。左边的 ``"total_return"`` 是指标名称，
        # 右边的 ``total_return(equity_series)`` 是实际计算出来的值。
        "total_return": total_return(equity_series),
        "cagr": cagr(equity_series, periods_per_year=periods_per_year),
        "annual_vol": annualized_volatility(returns_series, periods_per_year=periods_per_year),
        "max_drawdown": max_drawdown(equity_series),
        "sharpe_ratio": sharpe_ratio(
            returns_series,
            periods_per_year=periods_per_year,
            annual_risk_free_rate=annual_risk_free_rate,
        ),
    }


def format_performance_summary(summary: pd.DataFrame) -> pd.DataFrame:
    """Format a performance summary table for notebook display.

    ``performance_summary`` 返回的是便于继续计算的原始小数，例如 0.1234。
    在 Jupyter Notebook 中展示时，可以用这个函数转成 ``12.34%`` 这类更
    直观的字符串格式。

    Example
    -------
    .. code-block:: python

        summary = pd.DataFrame({"strategy": performance_summary(df["strategy_ret"])}).T
        format_performance_summary(summary)
    """
    formatted = summary.copy()
    for column in ["total_return", "cagr", "annual_vol", "max_drawdown"]:
        # 语法备注：
        # ``for column in [...]`` 会依次把列表里的每个字符串赋值给 column，
        # 然后执行缩进块里的代码。
        if column in formatted.columns:
            # 语法备注：
            # ``column in formatted.columns`` 判断这个列名是否存在于 DataFrame 中。
            formatted[column] = formatted[column].map(lambda value: f"{value:.2%}")
            # 语法备注：
            # ``lambda value: f"{value:.2%}"`` 是一个匿名小函数。
            # 它接收一个 value，并返回百分比字符串，例如 0.1234 -> "12.34%"。
            # ``.map(...)`` 会把这个匿名函数应用到这一列的每一个单元格。
    if "sharpe_ratio" in formatted.columns:
        formatted["sharpe_ratio"] = formatted["sharpe_ratio"].map(
            lambda value: "nan" if pd.isna(value) else f"{value:.2f}"
        )
        # 语法备注：
        # ``A if condition else B`` 是 Python 的条件表达式。
        # 这里意思是：如果 value 是缺失值，就显示 "nan"；
        # 否则把 value 格式化成保留两位小数的字符串。
    return formatted
