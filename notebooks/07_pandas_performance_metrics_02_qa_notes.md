# `07_pandas_performance_metrics_02.ipynb` 问答笔记

对应 Notebook：[07_pandas_performance_metrics_02.ipynb](07_pandas_performance_metrics_02.ipynb)

这份笔记整理本节围绕“年化波动率”和“夏普比率”的问答。Notebook 里的核心公式在 `07_pandas_performance_metrics_02.ipynb` 第 13-23 行，核心代码在第 61-73 行。

## 1. Python 怎么算波动率

波动率通常不是直接对价格 `close` 算标准差，而是对收益率算标准差。

```text
日波动率 = 日收益率标准差
年化波动率 = 日收益率标准差 * sqrt(252)
```

日线 ETF 数据通常用一年 `252` 个交易日估算。

最小写法：

```python
import numpy as np

ret = group["close"].pct_change()
daily_vol = ret.std(ddof=1)
annual_vol = daily_vol * np.sqrt(252)
```

多只 ETF 时必须先按 `symbol` 分组：

```python
df["ret"] = df.groupby("symbol")["close"].pct_change()

for symbol, group in df.groupby("symbol"):
    daily_vol = group["ret"].std(ddof=1)
    annual_vol = daily_vol * np.sqrt(252)

    print(symbol, f"日波动率: {daily_vol:.2%}", f"年化波动率: {annual_vol:.2%}")
```

### 为什么要先算收益率

价格本身有单位，例如 `1.0`、`3.5`、`100.0`。不同标的价格水平不同，直接比较价格标准差没有统一含义。

收益率是比例，例如 `1%`、`-0.5%`，不同标的之间更容易比较。

## 2. 夏普比率怎么算

夏普比率衡量的是：

```text
每承担一份波动，换来了多少收益
```

标准公式：

```text
Sharpe = 年化超额收益 / 年化波动率
```

日频数据中，常用写法是：

```text
Sharpe = 日均超额收益 / 日超额收益标准差 * sqrt(252)
```

如果暂时不考虑无风险利率：

```python
import numpy as np

ret = group["ret"].dropna()

sharpe = ret.mean() / ret.std(ddof=1) * np.sqrt(252)
```

更稳一点的写法：

```python
import numpy as np

ret = group["ret"].dropna()
daily_vol = ret.std(ddof=1)

if daily_vol == 0:
    sharpe = np.nan
else:
    sharpe = ret.mean() / daily_vol * np.sqrt(252)
```

## 3. `group["ret"].mean()/daily_vol*np.sqrt(252)` 的计算顺序

表达式：

```python
group["ret"].mean() / daily_vol * np.sqrt(252)
```

Python 会先执行函数和方法调用：

```python
group["ret"].mean()
np.sqrt(252)
```

然后再计算 `/` 和 `*`。

`/` 和 `*` 的优先级相同，所以从左到右计算：

```python
(group["ret"].mean() / daily_vol) * np.sqrt(252)
```

它不是：

```python
group["ret"].mean() / (daily_vol * np.sqrt(252))
```

为了可读性，建议主动加括号：

```python
sharpe_ratio = (group["ret"].mean() / daily_vol) * np.sqrt(252)
```

## 4. 两个夏普公式是否等价

这两个公式：

```text
夏普 = 年化超额收益 / 年化波动率
```

和：

```text
夏普 = 超额收益均值 / 超额收益标准差 * sqrt(252)
```

在常见日频夏普写法里是等价的，但有一个前提：

```text
年化超额收益 = 日超额收益均值 * 252
年化波动率 = 日超额收益标准差 * sqrt(252)
```

代入后：

```text
夏普
= 年化超额收益 / 年化波动率
= (日超额收益均值 * 252) / (日超额收益标准差 * sqrt(252))
= 日超额收益均值 / 日超额收益标准差 * sqrt(252)
```

所以它们等价。

## 5. 什么时候不严格等价

如果你把“年化超额收益”理解成 `CAGR` 或复利年化收益，再写：

```python
sharpe = cagr / annual_vol
```

这个结果不严格等于标准日频 Sharpe。

原因是：

- 标准日频 Sharpe 用的是“平均单期超额收益”年化。
- `CAGR` 是复利口径，计算逻辑不同。

`cagr / annual_vol` 不是完全没意义，但它不是最标准的日频夏普公式。

## 6. 按“年化超额收益 / 年化波动率”写代码

如果要明确写成：

```text
夏普 = 年化超额收益 / 年化波动率
```

可以这样写。

### 不考虑无风险利率

```python
import numpy as np

ret = group["ret"].dropna()

annual_excess_return = ret.mean() * 252
annual_vol = ret.std(ddof=1) * np.sqrt(252)

if annual_vol == 0:
    sharpe = np.nan
else:
    sharpe = annual_excess_return / annual_vol
```

这里虽然变量名叫 `annual_excess_return`，但因为没有减无风险利率，所以实际含义是“年化平均收益”。

### 考虑无风险利率

假设 `risk_free_rate` 是年化无风险利率，例如 `0.02` 表示年化 `2%`：

```python
import numpy as np

ret = group["ret"].dropna()

risk_free_rate = 0.02
periods_per_year = 252

daily_rf = risk_free_rate / periods_per_year
excess_ret = ret - daily_rf

annual_excess_return = excess_ret.mean() * periods_per_year
annual_vol = excess_ret.std(ddof=1) * np.sqrt(periods_per_year)

if annual_vol == 0:
    sharpe = np.nan
else:
    sharpe = annual_excess_return / annual_vol
```

也可以写成更短的等价形式：

```python
sharpe = excess_ret.mean() / excess_ret.std(ddof=1) * np.sqrt(252)
```

## 7. 当前 Notebook 里的代码对应关系

当前 Notebook 的核心代码大致是：

```python
df["ret"] = df.groupby("symbol")["close"].pct_change()

for symbol, group in df.groupby("symbol"):
    daily_vol = group["ret"].std()
    annual_vol = daily_vol * np.sqrt(252)
    sharpe_ratio = group["ret"].mean() / daily_vol * np.sqrt(252)
```

对应含义：

- `pct_change()`：计算每日收益率。
- `group["ret"].std()`：计算日收益率标准差，也就是日波动率。pandas 默认 `ddof=1`。
- `daily_vol * np.sqrt(252)`：计算年化波动率。
- `group["ret"].mean() / daily_vol * np.sqrt(252)`：计算简化版年化 Sharpe，不扣无风险利率。

建议改成更清晰的写法：

```python
ret = group["ret"].dropna()
daily_vol = ret.std(ddof=1)
annual_vol = daily_vol * np.sqrt(252)

if daily_vol == 0:
    sharpe_ratio = np.nan
else:
    sharpe_ratio = (ret.mean() / daily_vol) * np.sqrt(252)
```

## 8. 最容易记错的点

1. 波动率算的是收益率标准差，不是价格标准差。
2. 日频年化波动率是 `std * sqrt(252)`，不是 `std * 252`。
3. 夏普是倍数，不是百分比，所以显示成 `1.23`，不要显示成 `123%`。
4. `a / b * c` 的计算顺序是 `(a / b) * c`。
5. 标准日频 Sharpe 使用平均超额收益，不是 CAGR。
6. 多标的数据要先 `groupby("symbol")`，否则不同 ETF 会混在一起算。

