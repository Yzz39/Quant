"""Performance metric helpers for ETF/backtest study scripts.

This module provides small helper functions to compute drawdown-related
metrics from an equity / net-value series. The functions accept either a
``pandas.Series`` or any iterable of numbers.
"""

from __future__ import annotations  # 推迟类型注解求值（使注解在运行时为字符串）

from collections.abc import Iterable  # 用于类型注解，表示可迭代对象

import pandas as pd  # pandas 常用别名


def _to_equity_series(equity: pd.Series | Iterable[float]) -> pd.Series:
    """Convert an equity curve to numeric pandas Series and validate it.

    参数:
    - ``equity``: 可以是 ``pandas.Series`` 或任意可迭代的数字序列。

    返回值:
    - 一个经过数值化处理的 ``pandas.Series``，原始的缺失值会保留为 ``NaN``，
      但函数会在返回前对数据有效性进行校验（至少有一个非缺失值且所有有效值为正）。

    主要步骤说明（逐行对应实现）:
    1. 若输入已是 ``pd.Series``，使用 ``copy()`` 创建副本以避免修改原对象。
    2. 否则，将可迭代对象消费为列表并用 ``pd.Series`` 构造序列。
    3. 使用 ``pd.to_numeric(..., errors='coerce')`` 强制把元素转为数值，无法转换的变为 ``NaN``。
    4. 用 ``dropna()`` 得到有效（非缺失）值子序列用于验证。
    5. 如果没有任何有效值或存在非正值（<= 0），抛出 ``ValueError``。
    6. 返回已数值化的 ``series``（仍包含原始位置的 NaN）。
    """
    # 如果已经是 pandas Series，复制以免修改调用者的数据
    if isinstance(equity, pd.Series):
        series = equity.copy()
    else:
        # 把任意可迭代对象显式转为 list，然后构造 Series
        series = pd.Series(list(equity))

    # 将所有元素尝试转换为数值类型，无法转换的设为 NaN
    series = pd.to_numeric(series, errors="coerce")
    # 删除缺失值以便进行有效性检查
    valid = series.dropna()

    # 检查至少存在一个非缺失值
    if valid.empty:
        raise ValueError("equity must contain at least one non-missing value")
    # 检查所有有效值均为正（净值/权益一般为正数）
    if (valid <= 0).any():
        raise ValueError("equity values must be positive")

    # 返回经过数值化转换但保留 NaN 的原始 series
    return series


def drawdown_curve(equity: pd.Series | Iterable[float]) -> pd.Series:
    """Return the drawdown curve of an equity/net-value series.

    计算方式（向量化）::

        drawdown_t = current_equity_t / running_peak_t - 1

    解释:
    - 当序列创下新高时，当前值等于历史运行峰值，结果为 0。
    - 低于历史峰值时，结果为负数，代表回撤幅度（相对于峰值的百分比）。
    - 函数会保留输入中的缺失值（NaN），并且在计算累积最大值时忽略 NaN，
      这与 pandas 的 ``cummax`` 行为一致。
    """
    # 先将输入规范化为 pandas Series 并验证
    series = _to_equity_series(equity)
    # 计算到当前为止的历史最高值（逐点的累积最大值）
    running_peak = series.cummax()
    # 逐点计算 drawdown（向量化运算），NaN 会被保留
    result = series / running_peak - 1.0
    # 给返回的 Series 命名，便于显示或合并
    result.name = "drawdown"
    return result


def max_drawdown(equity: pd.Series | Iterable[float]) -> float:
    """Return the maximum drawdown as the worst negative value in the curve.

    实现细节:
    - 先用 ``drawdown_curve`` 得到逐点回撤序列，然后取最小值（最深的回撤）。
    - 最终将结果转换为 Python 的原生 ``float`` 并返回。
    """
    return float(drawdown_curve(equity).min())
