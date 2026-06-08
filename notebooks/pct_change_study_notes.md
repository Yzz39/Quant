# `pct_change()` 学习笔记

`pct_change()` 看起来只是一行代码，但它背后是量化入门里非常核心的概念：用价格序列计算相邻两期收益率。

## 1. `pct_change()` 是什么

在 pandas 里：

```python
df["ret"] = df["close"].pct_change()
```

含义是：

```text
今日收益率 = 今日收盘价 / 昨日收盘价 - 1
ret[t] = close[t] / close[t-1] - 1
```

如果昨天收盘价是 `1.00`，今天收盘价是 `1.03`，那么今天收益率就是：

```text
1.03 / 1.00 - 1 = 0.03 = 3%
```

所以，`pct_change()` 输出的不是“百分号格式”，而是“小数形式的收益率”。

例如：

- `0.03` 代表 `3%`
- `-0.02` 代表 `-2%`

## 2. 为什么第一天收益率是空值

第一天没有“前一天”可以比较，所以第一行通常是 `NaN`。这不是错误，是正常现象。

例如：

| date | close | ret |
|---|---:|---:|
| 2024-01-01 | 1.00 | NaN |
| 2024-01-02 | 1.03 | 0.03 |
| 2024-01-03 | 1.02 | -0.009708 |

## 3. 使用前必须先按日期排序

这是最重要的注意事项之一。

错误示例：

```python
df["ret"] = df["close"].pct_change()
```

如果 CSV 日期顺序是乱的，或者是倒序的，那么 `pct_change()` 会按当前行顺序计算，而不是自动按日期计算。

正确做法：

```python
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")
df["ret"] = df["close"].pct_change()
```

要记住：

```text
pct_change() 不理解“时间”，它只看“上一行”。
```

## 4. 应该用哪个价格算收益率

最常见的是：

```python
df["ret"] = df["close"].pct_change()
```

也就是“收盘到收盘收益率”。

不同价格口径对应不同含义：

| 写法 | 含义 |
|---|---|
| `close.pct_change()` | 收盘到收盘收益率，最常用 |
| `open.pct_change()` | 开盘到开盘收益率 |
| `close / open - 1` | 当日开盘到收盘收益率 |
| `open / close.shift(1) - 1` | 昨收到今开盘的跳空收益 |

初学阶段建议先统一使用：

```python
df["ret"] = df["close"].pct_change()
```

不要一开始混用多种收益率口径，否则很容易把信号时点和交易价格搞乱。

## 5. 复权价格非常重要

ETF 如果发生分红、拆分、份额折算等情况，价格序列可能出现跳变。

所以计算长期收益率时，应该优先确认你使用的是不是这些字段：

- 前复权价格
- 后复权价格
- 复权净值
- `adj_close`

`pct_change()` 只负责根据价格计算变化率，它不知道价格跳变到底是真实涨跌，还是分红除权造成的。

因此，回测或研究前要先确认：

- `close` 是原始收盘价还是复权收盘价
- 数据源是否已经做过复权
- ETF 是否有净值字段可替代价格字段

回测说明里最好明确写清楚：

```text
本策略使用前复权 close 计算收益率。
```

## 6. 缺失值会影响结果

如果中间有缺失值，要先检查，不要急着自动填充。

例如：

| date | close |
|---|---:|
| 2024-01-01 | 1.00 |
| 2024-01-02 | NaN |
| 2024-01-03 | 1.03 |

建议先检查：

```python
df["close"].isna().sum()
```

再定位缺失行：

```python
missing_close = df[df["close"].isna()]
print(missing_close)
```

初学阶段不建议随手这样处理：

```python
df["close"] = df["close"].ffill()
```

因为这会默认“缺失日价格不变”，可能掩盖数据问题。

更稳妥的思路是：

```text
先发现问题，再决定是否修复。
```

## 7. 多 ETF 时不能直接整表 `pct_change()`

如果一个 CSV 里混着多只 ETF：

| date | symbol | close |
|---|---|---:|
| 2024-01-01 | 510300 | 4.00 |
| 2024-01-01 | 159915 | 2.00 |
| 2024-01-02 | 510300 | 4.04 |
| 2024-01-02 | 159915 | 2.02 |

不能直接写：

```python
df["ret"] = df["close"].pct_change()
```

否则可能拿 `159915` 的价格去和 `510300` 的价格比较，结果完全错误。

正确做法：

```python
df = df.sort_values(["symbol", "date"])
df["ret"] = df.groupby("symbol")["close"].pct_change()
```

核心原则：

```text
每只 ETF 只能和自己的上一期价格比较。
```

## 8. 收益率不是百分数，而是小数

`pct_change()` 输出的是小数：

- `0.01 = 1%`
- `0.10 = 10%`
- `-0.05 = -5%`

如果只是为了打印显示成百分比，可以写：

```python
print(df["ret"].map(lambda x: f"{x:.2%}"))
```

但在内部计算时，应该始终保留小数形式。

正确：

```text
3% -> 0.03
```

错误：

```text
3% -> 3
```

## 9. 日收益率可以累乘成净值曲线

如果已经有日收益率：

```python
df["equity"] = (1 + df["ret"]).cumprod()
```

含义是：

```text
把每天收益率转成增长倍数，再连续复利累乘。
```

第一天因为 `ret` 是空值，通常会写成：

```python
df["equity"] = (1 + df["ret"].fillna(0)).cumprod()
```

这表示第一天收益率记为 `0`，初始净值从 `1` 开始。

## 10. 不要把收益率和信号时点搞混

这是回测里非常重要的坑。

例如：

```python
df["ma20"] = df["close"].rolling(20).mean()
df["signal"] = df["close"] > df["ma20"]
```

如果直接写：

```python
df["strategy_ret"] = df["signal"] * df["ret"]
```

可能有未来函数问题。

原因是：

- `ret` 表示今天收盘相对昨天收盘的收益
- `signal` 却用了今天收盘价才能算出来

更合理的写法通常是：

```python
df["strategy_ret"] = df["signal"].shift(1) * df["ret"]
```

这表示：

```text
昨天收盘产生信号，今天持有并承担今天这段收益。
```

这是量化回测里非常基础的时点对齐原则。

## 11. 极端收益率要检查

ETF 通常不会频繁出现特别夸张的单日涨跌。

如果某天收益率特别异常，例如：

- `+50%`
- `-40%`

就要排查：

- 是否未复权
- 是否数据错误
- 是否单位写错
- 是否字段错位
- 是否换了标的
- 是否日期重复
- 是否排序错误

可以先做一个简单筛查：

```python
extreme = df[df["ret"].abs() > 0.12]
print(extreme)
```

这里的 `12%` 不是绝对规则，只是一个初步排查阈值。

## 12. 推荐的标准写法

单 ETF：

```python
import pandas as pd

df = pd.read_csv("etf_daily.csv")
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")
df["close"] = pd.to_numeric(df["close"], errors="coerce")
df["ret"] = df["close"].pct_change()

print(df[["date", "close", "ret"]].head())
```

多 ETF：

```python
import pandas as pd

df = pd.read_csv("etf_daily.csv")
df["date"] = pd.to_datetime(df["date"])
df["close"] = pd.to_numeric(df["close"], errors="coerce")
df = df.sort_values(["symbol", "date"])
df["ret"] = df.groupby("symbol")["close"].pct_change()

print(df[["symbol", "date", "close", "ret"]].head())
```

## 13. 你现在最需要记住的 5 个点

`pct_change()` 最重要的 5 个注意事项是：

1. 先按日期升序排序。
2. 确认 `close` 是数字类型。
3. 确认价格是否做过复权。
4. 多 ETF 必须 `groupby("symbol")`。
5. 做策略收益时，信号通常要 `shift(1)`。

一句话总结：

```text
pct_change() 只是工具，真正重要的是你要知道“上一期是谁”“价格口径是什么”“有没有偷看未来”。
```
