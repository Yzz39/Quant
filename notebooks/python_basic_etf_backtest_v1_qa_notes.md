# `python_basic_etf_backtest_v1.ipynb` 问答整理笔记

这份笔记整理了围绕 [python_basic_etf_backtest_v1.ipynb](/d:/quant/notebooks/python_basic_etf_backtest_v1.ipynb) 的核心问答，重点覆盖：

- CSV 检查与数据转换
- pandas 常见语法
- 收益率、持仓与时间对齐
- 净值曲线生成逻辑
- 绩效指标的算法与理解

## 1. 这个 notebook 在做什么

这个脚本是一个最小可运行的 ETF 回测练习版，主流程是：

1. 读取 ETF 日线 CSV
2. 检查字段和数据质量
3. 计算日收益率 `ret`
4. 计算 `MA20`
5. 生成 `signal`
6. 用 `shift(1)` 生成 `position`
7. 计算 `strategy_ret`
8. 生成净值曲线
9. 计算基础绩效指标

## 2. `etf_csv_check.py` 到底有没有“数据转换功能”

结论：

- `etf_csv_check.py` 有“检查过程中使用的解析转换能力”
- 但它没有“把清洗后的数据返回给 notebook 继续使用”的功能

更准确地说：

- 它会做列名标准化
- 它会尝试解析日期
- 它会尝试解析数值
- 但这些解析只用于检查

它不会做这些事：

- 不会返回 `DataFrame`
- 不会修改 notebook 里的 `df`
- 不会把清洗结果写回 CSV

所以 notebook 里虽然已经调用了：

```python
status = check_etf_csv(DATA_PATH)
```

后面仍然需要自己再做：

```python
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df[col] = pd.to_numeric(df[col], errors="coerce")
```

因为这一步才是真正把 `df` 转成后续回测可计算的格式。

## 3. 为什么 `check_etf_csv()` 之后还要再做类型转换

因为两者职责不同：

- `check_etf_csv()`：负责体检、报错、打印检查报告
- notebook 后续代码：负责把当前 `df` 真正转成 pandas 能直接计算的格式

可以这样理解：

```text
check_etf_csv() 判断“这份 CSV 能不能用”
pd.to_datetime / pd.to_numeric 负责“把当前 df 变成能算的样子”
```

## 4. `display(df[required_cols].isna().sum())` 是什么意思

这句代码：

```python
display(df[required_cols].isna().sum())
```

可以拆成 4 层：

### `df[required_cols]`

从 `df` 中选出必要字段。

例如：

```python
required_cols = ["date", "open", "high", "low", "close", "volume"]
```

那么：

```python
df[required_cols]
```

就等于选出这几列组成一个新的 `DataFrame`。

### `.isna()`

逐格判断是不是缺失值：

- 是缺失值 -> `True`
- 不是缺失值 -> `False`

### `.sum()`

对布尔值求和：

- `True` 会当成 `1`
- `False` 会当成 `0`

因此：

```python
df[required_cols].isna().sum()
```

表示统计每一列有多少个缺失值。

### `display(...)`

在 notebook 里把结果更清楚地展示出来。

一句话总结：

```text
选出必要字段 -> 判断空值 -> 按列统计空值个数 -> 展示出来
```

## 5. `axis=1` 是什么意思

例如这句：

```python
non_positive_price = df[(df[["open", "high", "low", "close"]] <= 0).any(axis=1)]
```

其中：

```python
.any(axis=1)
```

表示：

```text
按“行”检查，只要这一行里有一个值为 True，就返回 True
```

所以这整句的含义是：

```text
找出 open / high / low / close 中，只要任意一个价格 <= 0 的那些行
```

记忆方式：

- `axis=0`：按列
- `axis=1`：按行

## 6. `signal`、`position`、`ret` 之间的关系

这个 notebook 最重要的时间关系是：

```text
signal[t]   = 第 t 天收盘后才知道的信号
position[t] = 第 t-1 天信号决定的第 t 天持仓
ret[t]      = close[t] / close[t-1] - 1
strategy_ret[t] = position[t] * ret[t]
```

也就是：

- `signal` 是判断结果
- `position` 是实际持仓
- `ret[t]` 是昨天收盘到今天收盘这一段收益

因此不能直接写：

```python
df["strategy_ret"] = df["signal"] * df["ret"]
```

因为这会用今天收盘后才知道的信号，去赚今天已经发生的收益。

正确写法是：

```python
df["position"] = df["signal"].shift(1)
df["strategy_ret"] = df["position"] * df["ret"]
```

## 7. 净值曲线是怎么生成的

这两句：

```python
df["strategy_equity"] = (1 + df["strategy_ret"]).cumprod()
df["benchmark_equity"] = (1 + df["benchmark_ret"]).cumprod()
```

本质上是在做：

```text
把每天的收益率转成“增长倍数”，再连续复利累乘
```

例如某几天收益率是：

```text
0.02, -0.01, 0.03
```

那么：

```text
1 + ret -> 1.02, 0.99, 1.03
```

再做 `cumprod()`：

```text
第1天: 1.02
第2天: 1.02 * 0.99
第3天: 1.02 * 0.99 * 1.03
```

这就是净值曲线。

一句话总结：

```text
净值曲线 = (1 + 收益率序列) 的累计连乘
```

## 8. `max_drawdown()` 里是不是隐含了遍历

是的，隐含了遍历。

代码：

```python
def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    return drawdown.min()
```

虽然没有写 `for`，但这些 pandas 操作底层都会逐项处理：

- `cummax()`：从头到尾扫描，记录到当前为止的历史最高净值
- `equity / running_max - 1`：逐项计算当前回撤
- `min()`：再遍历一遍，找最小值

### 为什么回撤要取 `min()`

因为回撤定义是：

```text
drawdown = 当前净值 / 历史最高净值 - 1
```

所以：

- 创新高时回撤 = `0`
- 跌下去时回撤是负数
- 跌得越深，值越小

因此“最大回撤”虽然名字叫最大，但在数值上要取最小值。

例如：

```text
drawdown = [0.00, -0.03, -0.08, -0.02]
```

最大回撤就是：

```text
-0.08
```

## 9. `ret.std(ddof=1)` 里的 `ddof=1` 是什么

标准差里的分母写法是：

```text
方差 = 偏差平方和 / (n - ddof)
```

所以：

- `ddof=0`：除以 `n`
- `ddof=1`：除以 `n-1`

区别：

- `ddof=0`：通常看作总体标准差
- `ddof=1`：通常看作样本标准差

而且：

```text
ddof=1 算出来通常会略大一点
```

特别是样本很少时更明显。

### `ret.std(ddof=1)` 是对哪些数据算

是对 `ret` 这一整列当前所有非空数据计算标准差。

如果前面先写了：

```python
ret = ret.fillna(0)
```

那么被填成 `0` 的那些值也会被一起算进去。

## 10. 为什么 Sharpe 公式里没有减无风险收益率

代码里写的是：

```python
sharpe = np.nan if vol == 0 else ret.mean() / ret.std(ddof=1) * np.sqrt(periods_per_year)
```

这不是最严格的 Sharpe，而是一个教学版简化写法。

标准定义是：

```text
Sharpe = (投资组合收益率 - 无风险收益率) / 投资组合波动率
```

如果用日收益率表示，更严格的日频版本应该是：

```text
Sharpe = (日均收益率 - 日无风险收益率) / 日收益率标准差 * sqrt(252)
```

而 notebook 里这一版默认近似成：

```text
无风险收益率 = 0
```

所以变成：

```text
Sharpe ≈ 日均收益率 / 日收益率标准差 * sqrt(252)
```

这也是为什么列名用了：

```python
"sharpe_no_rf"
```

意思就是“不扣无风险利率的简化版 Sharpe”。

## 11. 绩效指标区块都在算什么

代码里主要算了这些指标：

### 总收益率 `total_return`

公式：

```text
总收益率 = 期末净值 / 期初净值 - 1
```

### 年化收益率 `cagr`

公式：

```text
CAGR = 期末净值 ^ (一年交易日数 / 样本天数) - 1
```

### 年化波动率 `annual_vol`

公式：

```text
年化波动率 = 日收益率标准差 * sqrt(252)
```

### 最大回撤 `max_drawdown`

公式：

```text
最大回撤 = min(当前净值 / 历史最高净值 - 1)
```

### 简化版 Sharpe `sharpe_no_rf`

公式：

```text
Sharpe ≈ 日均收益率 / 日收益率标准差 * sqrt(252)
```

## 12. `summary = pd.DataFrame(...).T` 是什么意思

这段：

```python
summary = pd.DataFrame({
    "strategy": performance_summary(df["strategy_ret"], df["strategy_equity"]),
    "benchmark": performance_summary(df["benchmark_ret"], df["benchmark_equity"]),
}).T
```

含义是：

- 先分别算出 `strategy` 和 `benchmark` 的绩效指标字典
- 再把这两个字典拼成 `DataFrame`
- 最后的 `.T` 表示转置

转置后更容易读：

- 行：`strategy`、`benchmark`
- 列：`total_return`、`cagr`、`annual_vol`、`max_drawdown`、`sharpe_no_rf`

## 13. 为什么最后要格式化成百分比

这段：

```python
for col in ["total_return", "cagr", "annual_vol", "max_drawdown"]:
    summary[col] = summary[col].map(lambda x: f"{x:.2%}")
summary["sharpe_no_rf"] = summary["sharpe_no_rf"].map(lambda x: f"{x:.2f}")
```

含义是：

- 收益率、年化收益率、波动率、最大回撤这些本质上是比例，显示成百分比更直观
- Sharpe 是倍数，不是百分比，所以保留两位小数即可

## 14. 这个 notebook 里最值得记住的几个点

### 数据检查

- `check_etf_csv()` 负责体检，不负责返回清洗后的 `DataFrame`
- 真正进入计算前，仍要自己做 `to_datetime` 和 `to_numeric`

### pandas 语法

- `df[cols]`：选列
- `.isna()`：判断空值
- `.sum()`：统计数量
- `.any(axis=1)`：按行判断
- `.iloc[0]` / `.iloc[-1]`：按位置取第一个 / 最后一个

### 回测时点

- `signal` 是判断结果
- `position` 是实际持仓
- `ret[t]` 是昨天收盘到今天收盘的收益
- `position[t] = signal[t-1]` 才能避免未来函数

### 净值与绩效

- 净值曲线来自 `(1 + ret).cumprod()`
- 最大回撤来自历史最高净值比较
- 波动率通常用 `std * sqrt(252)` 年化
- 当前 notebook 用的是“不扣无风险利率”的简化版 Sharpe

## 15. 一句话总复盘

这份 notebook 的核心，不只是“把代码跑通”，而是理解下面这条链条：

```text
数据能不能用 -> 收益率怎么算 -> 信号什么时候产生 -> 持仓什么时候生效 -> 净值怎么累乘 -> 指标怎么解释
```

只要这条链条想清楚，后面的均线择时、轮动、风控、绩效分析就会顺很多。
