# `rolling()` 均线学习笔记

`rolling()` 均线的核心不是“会写代码”，而是要理解：

```text
窗口里到底包含哪些数据。
```

很多初学者会被“20 日均线”这几个字绕晕，但本质上它只是：

```text
用最近 N 个交易日的价格取平均。
```

## 1. 什么是 `rolling` 均线

假设你有一列收盘价 `close`：

| date | close |
|---|---:|
| 2024-01-01 | 10 |
| 2024-01-02 | 11 |
| 2024-01-03 | 12 |
| 2024-01-04 | 13 |
| 2024-01-05 | 14 |

如果计算 3 日均线：

```python
df["ma3"] = df["close"].rolling(3).mean()
```

含义是：

```text
ma3 = 最近 3 行 close 的平均值
```

也就是：

- 第 3 天 `ma3 = (第 1 天 + 第 2 天 + 第 3 天) / 3`
- 第 4 天 `ma3 = (第 2 天 + 第 3 天 + 第 4 天) / 3`
- 第 5 天 `ma3 = (第 3 天 + 第 4 天 + 第 5 天) / 3`

## 2. `window` 是什么意思

```python
rolling(20)
```

这里面的 `20` 不是“20 个自然日”，而是：

```text
当前行往前数，包含当前行在内的最近 20 条数据。
```

对于日线 ETF 来说，通常就是：

```text
最近 20 个交易日。
```

注意：

- 不是最近 20 天自然日
- 周末和节假日没有交易数据，所以不会进入窗口

## 3. 手工例子：3 日均线

假设：

| date | close |
|---|---:|
| 01-01 | 10 |
| 01-02 | 11 |
| 01-03 | 12 |
| 01-04 | 13 |
| 01-05 | 14 |

计算：

```python
df["ma3"] = df["close"].rolling(3).mean()
```

结果：

| date | close | ma3 |
|---|---:|---:|
| 01-01 | 10 | NaN |
| 01-02 | 11 | NaN |
| 01-03 | 12 | 11 |
| 01-04 | 13 | 12 |
| 01-05 | 14 | 13 |

为什么前两天是 `NaN`？

- `01-01` 只有 1 个 `close`，不够 3 个
- `01-02` 只有 2 个 `close`，不够 3 个
- 到 `01-03` 才凑够 3 个数据

## 4. `rolling(3).mean()` 的窗口移动过程

可以把窗口想成一个每天向前滑动的小盒子：

```text
第1天: [10]                  不够3个 -> NaN
第2天: [10, 11]              不够3个 -> NaN
第3天: [10, 11, 12]          平均 = 11
第4天:     [11, 12, 13]      平均 = 12
第5天:         [12, 13, 14]  平均 = 13
```

核心理解：

```text
窗口每天向前滑动一格，每次都重新取最近 N 条数据做平均。
```

## 5. 默认包含“当天数据”

这是最重要的知识点之一。

```python
df["ma20"] = df["close"].rolling(20).mean()
```

第 `t` 天的 `ma20` 默认包含第 `t` 天的 `close`。

也就是：

```text
ma20[t] = close[t-19] 到 close[t] 的平均值
```

所以如果你用今天收盘价算了今天的 `MA20`，再说“今天收盘前我就根据 MA20 买入”，那就可能有时点问题。

## 6. 回测里要小心未来函数

例如：

```python
df["ma20"] = df["close"].rolling(20).mean()
df["signal"] = df["close"] > df["ma20"]
df["strategy_ret"] = df["signal"] * df["ret"]
```

这通常不够严谨。

原因是：

- `signal` 用到了今天的收盘价 `close[t]`
- `ret[t]` 是今天从昨收到今收的收益
- 这等于用今天收盘后才知道的信息，去吃今天已经发生的收益

更合理的写法通常是：

```python
df["signal"] = df["close"] > df["ma20"]
df["strategy_ret"] = df["signal"].shift(1) * df["ret"]
```

含义是：

```text
今天收盘产生信号，明天才开始持有。
```

或者说：

```text
昨天的信号，赚今天的收益。
```

这是量化回测里非常重要的原则。

## 7. `min_periods` 是什么

默认情况下：

```python
df["ma20"] = df["close"].rolling(20).mean()
```

必须满 20 个数据才会计算，否则就是 `NaN`。

你也可以写：

```python
df["ma20"] = df["close"].rolling(20, min_periods=1).mean()
```

这表示：

```text
哪怕只有 1 个数据，也先开始计算平均值。
```

例如：

```text
close: 10, 11, 12
```

如果是 `ma3` 且 `min_periods=1`，那么：

- 第 1 天 = `10`
- 第 2 天 = `(10 + 11) / 2 = 10.5`
- 第 3 天 = `(10 + 11 + 12) / 3 = 11`

初学回测时更建议先用默认设置：

```python
rolling(20).mean()
```

也就是：

```text
不满窗口就不算。
```

这样更清晰，也不容易误解。

## 8. 常见均线窗口的含义

| 均线 | 含义 | 大概对应 |
|---|---|---|
| MA5 | 最近 5 个交易日平均价 | 约 1 周 |
| MA10 | 最近 10 个交易日平均价 | 约 2 周 |
| MA20 | 最近 20 个交易日平均价 | 约 1 个月 |
| MA60 | 最近 60 个交易日平均价 | 约 1 个季度 |
| MA120 | 最近 120 个交易日平均价 | 约半年 |
| MA250 | 最近 250 个交易日平均价 | 约 1 年 |

注意：

```text
这里说的是交易日，不是自然日。
```

## 9. 均线在策略里常用来做什么

### 用法 1：趋势过滤

```python
df["ma20"] = df["close"].rolling(20).mean()
df["signal"] = df["close"] > df["ma20"]
```

含义：

```text
收盘价在 20 日均线上方，认为短期趋势偏强。
```

### 用法 2：长短均线交叉

```python
df["ma20"] = df["close"].rolling(20).mean()
df["ma60"] = df["close"].rolling(60).mean()
df["signal"] = df["ma20"] > df["ma60"]
```

含义：

```text
短期平均价格高于长期平均价格，认为趋势向上。
```

### 用法 3：动量 / 风控过滤

例如 ETF 轮动里：

```python
df["ma120"] = df["close"].rolling(120).mean()
df["risk_on"] = df["close"] > df["ma120"]
```

含义：

```text
只有当 ETF 在 120 日均线上方，才允许买入。
```

## 10. 多 ETF 时要 `groupby`

如果一个 CSV 里有多只 ETF，不能直接写：

```python
df["ma20"] = df["close"].rolling(20).mean()
```

因为不同 ETF 的数据可能会串在一起。

正确写法：

```python
df = df.sort_values(["symbol", "date"])
df["ma20"] = df.groupby("symbol")["close"].transform(
    lambda x: x.rolling(20).mean()
)
```

含义是：

```text
每只 ETF 单独计算自己的 20 日均线。
```

## 11. 学习时最需要掌握的关键点

你现在重点记住这 7 个：

1. `rolling(N)` 表示最近 `N` 条数据。
2. 日线里这个 `N` 通常是 `N` 个交易日。
3. 默认窗口包含当前行。
4. 不满 `N` 个数据时，默认结果是 `NaN`。
5. `rolling(N).mean()` 就是 `N` 日简单移动平均。
6. 多 ETF 要按 `symbol` 分组计算。
7. 回测用信号时，通常要 `shift(1)`，避免偷看未来。

## 12. 最标准的单 ETF 写法

```python
import pandas as pd

df = pd.read_csv("etf_daily.csv")
df["date"] = pd.to_datetime(df["date"])
df["close"] = pd.to_numeric(df["close"], errors="coerce")
df = df.sort_values("date")

df["ma20"] = df["close"].rolling(20).mean()
df["ma60"] = df["close"].rolling(60).mean()
df["ret"] = df["close"].pct_change()
df["signal"] = df["close"] > df["ma20"]

# 昨天的信号，赚今天的收益
df["strategy_ret"] = df["signal"].shift(1) * df["ret"]
```

## 13. 一句话总结

```text
rolling 均线就是“用最近 N 个交易日的价格取平均”，窗口默认包含当天；做回测时，如果信号用到了当天收盘价，就要小心用 shift(1) 避免未来函数。
```

这个知识点一旦吃透，后面的 `MA20` 择时、`MA60` 趋势过滤、ETF 动量风控，都会顺很多。
