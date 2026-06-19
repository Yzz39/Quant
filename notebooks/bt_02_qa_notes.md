# bt_02：vectorbt 批量扫描均线参数学习笔记

对应 Notebook：[bt_02.ipynb](/d:/Quant/notebooks/bt_02.ipynb)

这份笔记整理我们围绕 `bt_02.ipynb` 的几个重点问答。核心主题是：如何用一组模拟收盘价，批量计算不同窗口的移动平均线，生成交易信号，并用 `vectorbt` 批量回测不同均线参数。

## 1. 构造一组可复现的模拟价格

代码：

```python
np.random.seed(42)

dates = pd.bdate_range("2023-01-02", periods=320)
trend = np.linspace(0, 0.35, len(dates))
cycle = 0.08 * np.sin(np.linspace(0, 8 * np.pi, len(dates)))
noise = np.random.normal(0, 0.012, len(dates)).cumsum()

close = pd.Series(100 * np.exp(trend + cycle + noise), index=dates, name="close")
close.head()
```

这段代码不是下载真实行情，而是人工构造一条“像价格”的收盘价序列，方便学习回测流程。

`np.random.seed(42)` 用来固定随机种子，让每次运行得到同一组随机数，便于复现实验。

`pd.bdate_range("2023-01-02", periods=320)` 生成 320 个工作日日期索引。这里的 `bdate_range` 默认跳过周末，更接近交易日序列。

`trend` 是长期趋势，从 `0` 平滑增加到 `0.35`，表示价格整体有向上漂移。

`cycle` 是周期波动，用 `sin` 模拟价格的阶段性起伏，`0.08` 控制波动幅度。

`noise` 是随机噪声，每天生成一个小的随机冲击，再用 `.cumsum()` 累加成类似随机游走的扰动。

最后：

```python
close = pd.Series(100 * np.exp(trend + cycle + noise), index=dates, name="close")
```

把 `trend + cycle + noise` 当成对数价格变化，再用 `np.exp(...)` 转成始终为正的价格。初始量级在 `100` 附近。

## 2. 批量计算移动平均线

代码：

```python
windows = np.array([5, 10, 20, 30, 60, 90, 120, 200])

ma = vbt.MA.run(close, window=windows)
ma_values = ma.ma
```

`vbt.MA.run(close, window=windows)` 的意思是：用 vectorbt 的 `MA` 指标，根据 `close` 这组收盘价，一次性计算多组移动平均线。

这里的 `windows` 包含多个窗口：

```text
5日均线
10日均线
20日均线
30日均线
60日均线
90日均线
120日均线
200日均线
```

所以 `ma` 不是一条均线，而是一个 vectorbt 指标对象，里面保存了多组参数的计算结果和相关元信息。

`ma.ma` 是 Python 的属性访问写法：

```python
对象.属性
```

在这里：

```python
ma_values = ma.ma
```

意思是：从 `ma` 这个指标对象中，取出真正的均线数值表。由于传入了多个窗口，`ma_values` 通常是一个 DataFrame，每一列对应一个 window。

## 3. `[20]` 代表什么

代码：

```python
ma_values[20]
raw_entries[20]
entries[20]
raw_exits[20]
exits[20]
```

这里的 `[20]` 可以先类比成按 key 取值，但更准确地说，它是 pandas DataFrame 的列标签。

因为前面批量计算了这些窗口：

```python
windows = np.array([5, 10, 20, 30, 60, 90, 120, 200])
```

所以 `ma_values`、`raw_entries`、`entries`、`raw_exits`、`exits` 这些对象里都有多列，每一列对应一个窗口参数。

因此：

```python
ma_values[20]
```

意思是取出列名为 `20` 的那一列，也就是 20 日均线。

它不是“取第 20 列”，而是“取 column label 等于 20 的列”。

可以类比成：

```python
data = {
    5: "5日均线",
    10: "10日均线",
    20: "20日均线",
}

data[20]
```

结果是：

```text
"20日均线"
```

## 4. 信号预览表 `signal_preview`

代码：

```python
signal_preview = pd.concat(
    {
        "close": close,
        "ma_20": ma_values[20],
        "raw_entry_20": raw_entries[20],
        "entry_20_after_shift": entries[20],
        "raw_exit_20": raw_exits[20],
        "exit_20_after_shift": exits[20],
    },
    axis=1,
)
```

这段是在构造一个信号检查表，专门拿 `20日均线` 这组参数出来看。

各列含义：

```python
"close": close
```

收盘价。

```python
"ma_20": ma_values[20]
```

20 日移动平均线。

```python
"raw_entry_20": raw_entries[20]
```

原始买入信号。当 `close` 向上穿过 20 日均线时为 `True`。

```python
"entry_20_after_shift": entries[20]
```

延后一天后的买入信号。这样做是为了避免“今天收盘后才知道信号，却假设今天已经买入”的未来函数问题。

```python
"raw_exit_20": raw_exits[20]
```

原始卖出信号。当 `close` 向下跌破 20 日均线时为 `True`。

```python
"exit_20_after_shift": exits[20]
```

延后一天后的卖出信号。

`pd.concat(..., axis=1)` 的意思是把这些 Series 按列拼成一个 DataFrame。`axis=1` 表示横向拼接，也就是增加列。

这个表主要不是用来回测，而是用来人工检查信号是否合理：原始信号在哪天出现，实际用于交易的信号是否正确延后了一天。

## 5. 年化收益率 `portfolio.annualized_return()`

代码：

```python
"annualized_return": portfolio.annualized_return()
```

`portfolio.annualized_return()` 表示年化收益率。

它回答的问题是：

```text
如果这段回测期间的收益表现按同样速度延续一年，大概相当于一年赚多少比例？
```

因为 `portfolio` 是用多组均线窗口批量回测出来的，所以它通常返回的不是单个数字，而是一组按窗口排列的结果，例如：

```text
5      0.123
10     0.156
20     0.098
30     0.071
60     0.044
90     0.032
120    0.018
200    NaN
```

这里的 `0.123` 表示约 `12.3%`，因为 vectorbt 这类指标通常用小数表示比例。

如果想看成百分比，可以写：

```python
portfolio.annualized_return() * 100
```

它和 `portfolio.total_return()` 不一样：

```text
total_return        整个回测期间总共赚了多少
annualized_return   把这段收益按时间长度折算成一年赚多少
```

## 6. 净值曲线图 `portfolio.value().plot(...)`

代码：

```python
portfolio.value().plot(title="MA parameter scan - portfolio value")
```

这行代码的功能是：把回测得到的账户净值曲线画出来。

拆开看：

```python
portfolio.value()
```

表示取出每一天的账户总价值，也就是：

```text
现金 + 当前持仓市值
```

如果初始资金是：

```python
init_cash=10_000
```

那么净值曲线通常会从 `10000` 附近开始。

因为这里是批量参数扫描，所以 `portfolio.value()` 通常会返回一个 DataFrame。每一列对应一个均线窗口参数，例如：

```text
window        5        10       20       30
date
2023-01-02    10000    10000    10000    10000
2023-01-03    10020    10000    10000    10000
...
```

然后：

```python
.plot(title="MA parameter scan - portfolio value")
```

负责画图，并给图表设置标题。

整句可以理解成：

```text
把不同均线参数策略的账户净值曲线画出来，图标题叫
"MA parameter scan - portfolio value"。
```

这张图可以用来观察不同参数组合的资金曲线差异，比如谁增长更好、谁波动更大、谁回撤更明显。

## 7. 学习时最容易混淆的点

`ma` 和 `ma.ma` 不一样：

```text
ma      是 vectorbt 指标对象
ma.ma   是真正的均线数值
```

`[20]` 不是第 20 个位置，而是列标签为 `20` 的那一列。

`raw_entries` 和 `entries` 不一样：

```text
raw_entries   原始信号，当天收盘后才能确认
entries       shift(1) 后的交易信号，下一天再使用
```

`total_return` 和 `annualized_return` 不一样：

```text
total_return        回测区间总收益
annualized_return   折算成年化后的收益
```

`portfolio.value()` 只是取出净值数据，不会重新运行回测。

