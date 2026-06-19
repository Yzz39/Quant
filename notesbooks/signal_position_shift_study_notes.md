# `signal`、`position` 与 `shift(1)` 学习笔记

这个知识点的核心是：

```text
信号什么时候产生，持仓什么时候生效，收益是哪一段时间产生的。
```

`shift()` 不是为了“代码好看”，而是为了把这三个时间点对齐。  
如果这里搞错，回测结果就会虚高，风险很大。

## 1. 先分清两个概念：`signal` 和 `position`

很多初学者会把它们混在一起，但它们不是一回事。

### `signal`：信号

信号是你根据数据判断出来的结果。

例如：

```python
df["signal"] = df["close"] > df["ma20"]
```

含义是：

```text
今天收盘价 > 今天 20 日均线
```

也就是：

```text
今天收盘后，我判断明天应该持有。
```

所以，`signal` 是“判断结果”。

### `position`：持仓

持仓是你在某一段收益期间是否真的持有。

例如：

- `position = 1` 表示持有 ETF
- `position = 0` 表示空仓

策略收益通常写成：

```python
df["strategy_ret"] = df["position"] * df["ret"]
```

这里的 `position[t]` 必须表示：

```text
在 ret[t] 这段收益期间，我是否已经持有。
```

## 2. `ret[t]` 到底是哪一段收益

如果你这样算日收益率：

```python
df["ret"] = df["close"].pct_change()
```

那么：

```text
ret[t] = close[t] / close[t-1] - 1
```

它代表的是：

```text
从昨天收盘 close[t-1] 到今天收盘 close[t] 的收益。
```

所以，`ret[t]` 不是“今天收盘之后的收益”，而是：

```text
昨天收盘后 -> 今天收盘前
```

这段已经发生完的收益。

## 3. 为什么需要 `shift(1)`

如果信号是用今天收盘价算出来的：

```python
df["signal"] = df["close"] > df["ma20"]
```

那么 `signal[t]` 要到今天收盘后才知道。

但 `ret[t]` 是：

```text
昨天收盘到今天收盘
```

这段收益。

所以不能直接写：

```python
df["strategy_ret"] = df["signal"] * df["ret"]
```

因为这相当于：

```text
用今天收盘后才知道的 signal[t]
去决定今天白天是否持有
然后赚到 ret[t]
```

这就是偷看未来。

## 4. 正确做法：昨天的信号决定今天的持仓

应该写：

```python
df["position"] = df["signal"].shift(1)
df["strategy_ret"] = df["position"] * df["ret"]
```

含义是：

```text
position[t] = signal[t-1]
```

也就是：

```text
昨天收盘后生成的信号，决定今天是否持有。
```

时间线可以这样理解：

```text
昨天收盘
  ↓
计算昨天的 signal[t-1]
  ↓
决定今天的 position[t]
  ↓
今天从昨收到今收产生 ret[t]
  ↓
strategy_ret[t] = position[t] × ret[t]
```

这样才没有未来函数。

## 5. 一个极简表格：错误写法为什么不对

假设有这样一组数据：

| 日期 | close | ma20 | signal = close > ma20 | ret |
|---|---:|---:|---|---:|
| 周一 | 10.0 | 9.8 | True | +1.00% |
| 周二 | 10.5 | 10.1 | True | +5.00% |
| 周三 | 10.2 | 10.3 | False | -2.86% |
| 周四 | 10.4 | 10.25 | True | +1.96% |

如果错误地写成：

```python
df["strategy_ret"] = df["signal"] * df["ret"]
```

结果逻辑会变成：

| 日期 | signal | ret | strategy_ret |
|---|---|---:|---:|
| 周一 | True | +1.00% | +1.00% |
| 周二 | True | +5.00% | +5.00% |
| 周三 | False | -2.86% | 0.00% |
| 周四 | True | +1.96% | +1.96% |

这里最不合理的是周三：

```text
周三收盘后你才知道 signal = False，
但你却用它躲开了周三当天已经发生的 -2.86%。
```

这在时间上说不通。

## 6. 正确写法的逻辑

应该写：

```python
df["position"] = df["signal"].shift(1)
df["strategy_ret"] = df["position"] * df["ret"]
```

结果逻辑会变成：

| 日期 | 昨天信号 | position | 今天 ret | strategy_ret |
|---|---|---|---:|---:|
| 周一 | - | NaN / 0 | +1.00% | NaN / 0 |
| 周二 | True | True | +5.00% | +5.00% |
| 周三 | True | True | -2.86% | -2.86% |
| 周四 | False | False | +1.96% | 0.00% |

这才合理：

- 周二收益由周一信号决定
- 周三收益由周二信号决定
- 周四收益由周三信号决定

## 7. `shift(1)` 到底做了什么

假设原始信号是：

| date | signal |
|---|---|
| 周一 | True |
| 周二 | True |
| 周三 | False |
| 周四 | True |

执行：

```python
df["position"] = df["signal"].shift(1)
```

得到：

| date | signal | position |
|---|---|---|
| 周一 | True | NaN |
| 周二 | True | True |
| 周三 | False | True |
| 周四 | True | False |

也就是：

```text
今天的 position = 昨天的 signal
```

这就是 `shift(1)` 的意义。

## 8. 常见模板

### 模板 A：收盘后生成信号，下一交易日持有

这是最应该先掌握的模板。

```python
df["ret"] = df["close"].pct_change()
df["ma20"] = df["close"].rolling(20).mean()
df["signal"] = df["close"] > df["ma20"]
df["position"] = df["signal"].shift(1).fillna(False)
df["strategy_ret"] = df["position"] * df["ret"]
```

解释：

- 今天收盘后判断趋势
- 明天按这个信号持有
- 所以用昨天的 `signal` 乘今天的 `ret`

### 模板 B：多 ETF 时，每只 ETF 单独 `shift`

如果有多只 ETF，不能整张表直接：

```python
df["position"] = df["signal"].shift(1)
```

因为不同 ETF 的信号会串起来。

正确写法：

```python
df = df.sort_values(["symbol", "date"])
df["position"] = df.groupby("symbol")["signal"].shift(1).fillna(False)
df["strategy_ret"] = df["position"] * df["ret"]
```

含义是：

```text
每只 ETF 用自己的昨天信号，决定自己的今天持仓。
```

## 9. 什么叫“无未来函数”

简单说：

```text
在第 t 天做决策时，只能使用第 t 天当时已经知道的信息，
不能使用未来才知道的信息。
```

对于日线收盘策略：

- 如果你在今天收盘后计算信号，那么可以用今天收盘价
- 也可以用今天的 `MA20`
- 但只能从明天开始执行
- 不能倒回去赚今天已经发生的收益

所以无未来函数的原则是：

```text
信息产生时间 <= 决策时间 <= 交易执行时间 <= 收益产生时间
```

不能反过来。

## 10. 最重要的公式

如果：

```text
ret[t] = close[t] / close[t-1] - 1
```

并且：

```text
signal[t] = 用 close[t] 生成
```

那么就应该有：

```text
position[t] = signal[t-1]
strategy_ret[t] = position[t] * ret[t]
```

代码就是：

```python
df["position"] = df["signal"].shift(1)
df["strategy_ret"] = df["position"] * df["ret"]
```

## 11. 一个容易混淆的点

`shift(1)` 不是说“收益延迟一天”，而是说：

```text
让今天的持仓使用昨天已经知道的信号。
```

也就是说，它修正的是：

```text
信号和收益之间的时间错位。
```

## 12. 最小完整示例

```python
df["ret"] = df["close"].pct_change()
df["ma20"] = df["close"].rolling(20).mean()

# 今天收盘后产生的信号
df["signal"] = df["close"] > df["ma20"]

# 明天才真正持有
df["position"] = df["signal"].shift(1).fillna(False)

# 今天策略收益 = 今天是否持有 × 今天 ETF 收益
df["strategy_ret"] = df["position"] * df["ret"]
```

## 13. 一句话总结

```text
signal 是“今天收盘后我想不想持有”，
position 是“今天这段收益里我实际有没有持有”；
shift(1) 的作用，就是让今天的持仓来自昨天的信号，
从而避免偷看今天收盘后才知道的信息。
```

只要把 `signal` 和 `position` 分开，很多回测逻辑就会一下子清楚很多。  
这个坎过去了，后面的净值曲线、最大回撤、调仓周期都会顺很多。
