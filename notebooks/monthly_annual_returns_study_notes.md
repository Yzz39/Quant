# 月度收益和年度收益表学习笔记

对应 Notebook：[06_pandas_performance_metrics_01.ipynb](06_pandas_performance_metrics_01.ipynb)

这份笔记整理“月度收益表”和“年度收益表”的实现逻辑，以及相关 Python / pandas 语法知识点。

## 1. 目标

目标是把日线收益率整理成两张表：

1. 月度收益表：每只 ETF、每一年、每个月的收益率。
2. 年度收益表：每一年、每只 ETF 的年度收益率。

核心实现位置：

- 准备 `returns_df`：[06_pandas_performance_metrics_01.ipynb 第 250 行](06_pandas_performance_metrics_01.ipynb#L250)
- 计算月度收益：[第 254 行](06_pandas_performance_metrics_01.ipynb#L254)
- 计算年度收益：[第 261 行](06_pandas_performance_metrics_01.ipynb#L261)
- 生成月度收益表：[第 268 行](06_pandas_performance_metrics_01.ipynb#L268)
- 生成年度收益表：[第 277 行](06_pandas_performance_metrics_01.ipynb#L277)

## 2. 前置数据：每日收益率

先读取日线数据，按标的和日期排序，然后按标的计算每日收益率：

```python
df = pd.read_csv("../data/sample_etf_daily.csv")

df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol", "date"], ascending=[True, True])
df["ret"] = df.groupby("symbol")["close"].pct_change()
```

关键点：

- `pd.read_csv(...)`：读取 CSV，返回 `DataFrame`。
- `pd.to_datetime(...)`：把日期字符串转成真正的日期类型。
- `sort_values(["symbol", "date"])`：保证每只 ETF 内部按日期升序排列。
- `groupby("symbol")["close"].pct_change()`：按 ETF 分组计算每日收益率。

每日收益率公式：

```text
ret[t] = close[t] / close[t-1] - 1
```

多标的场景必须先 `groupby("symbol")`，不能直接对全表 `close` 做 `pct_change()`。

## 3. `returns_df` 的结构

代码：

```python
returns_df = df.dropna(subset=["ret"]).copy()
returns_df["year"] = returns_df["date"].dt.year
returns_df["month"] = returns_df["date"].dt.month
```

执行完以后，`returns_df` 仍然是“一天一行”的日线 `DataFrame`，只是：

- 删除了 `ret` 为空的行。
- 新增了 `year` 列。
- 新增了 `month` 列。

用当前数据跑出来的结构是：

```text
shape: (1563, 12)
```

也就是：

```text
1563 行，12 列
```

主要列大概长这样：

```text
 symbol       date        close       ret      year   month
 159915   2023-01-03     2.193   -0.012607   2023      1
 159915   2023-01-04     2.151   -0.019152   2023      1
 159915   2023-01-05     2.135   -0.007438   2023      1
 159915   2023-01-06     2.092   -0.020141   2023      1
 159915   2023-01-09     2.149    0.027247   2023      1
```

最后几行类似：

```text
 symbol       date        close       ret      year   month
 511010   2024-12-24   112.596    0.000480   2024     12
 511010   2024-12-25   112.762    0.001474   2024     12
 511010   2024-12-26   112.359   -0.003574   2024     12
 511010   2024-12-27   112.343   -0.000142   2024     12
 511010   2024-12-30   112.060   -0.002519   2024     12
 511010   2024-12-31   112.129    0.000616   2024     12
```

例如：

```text
date = 2024-12-31
year = 2024
month = 12
```

后续分组就是靠 `symbol`、`year`、`month` 这几个字段完成的。

## 4. 为什么要 `dropna(subset=["ret"])`

每只 ETF 的第一天没有上一天价格，所以：

```python
pct_change()
```

会让每组第一行的 `ret` 变成 `NaN`。

这些行不能参与月度和年度收益聚合，所以先删除：

```python
returns_df = df.dropna(subset=["ret"]).copy()
```

其中：

- `dropna(subset=["ret"])`：只检查 `ret` 这一列是否为空。
- `.copy()`：复制一份新表，后面新增列时更稳，避免链式赋值警告。

## 5. 提取 `year` 和 `month`

```python
returns_df["year"] = returns_df["date"].dt.year
returns_df["month"] = returns_df["date"].dt.month
```

`.dt` 是 pandas 日期列的访问器。

- `.dt.year`：提取年份。
- `.dt.month`：提取月份。

前提是 `date` 必须已经通过 `pd.to_datetime()` 转成日期类型。

如果 `date` 还是普通字符串，`.dt.year` 和 `.dt.month` 会报错。

## 6. 月度收益怎么计算

代码：

```python
monthly_returns = (
    returns_df.groupby(["symbol", "year", "month"])["ret"]
    .apply(lambda ret: (1 + ret).prod() - 1)
    .rename("monthly_return")
    .reset_index()
)
```

分组逻辑：

```python
returns_df.groupby(["symbol", "year", "month"])["ret"]
```

含义是：

```text
每只 ETF / 每一年 / 每个月
```

每一组里是一组日收益率。

聚合逻辑：

```python
lambda ret: (1 + ret).prod() - 1
```

这是匿名函数，用来对每组日收益率计算复利收益。

核心公式：

```text
月度收益 = (1 + 第1天收益率) * (1 + 第2天收益率) * ... * (1 + 最后1天收益率) - 1
```

不能简单用：

```python
ret.sum()
```

因为收益率的跨期累计应该用复利连乘。

## 7. 年度收益怎么计算

代码：

```python
annual_returns = (
    returns_df.groupby(["symbol", "year"])["ret"]
    .apply(lambda ret: (1 + ret).prod() - 1)
    .rename("annual_return")
    .reset_index()
)
```

逻辑和月度收益一样，只是分组少了 `month`。

分组含义：

```text
每只 ETF / 每一年
```

年度收益公式：

```text
年度收益 = 年内所有日收益率复利连乘 - 1
```

## 8. `rename()` 和 `reset_index()` 的作用

```python
.rename("monthly_return")
.reset_index()
```

`rename("monthly_return")` 给计算结果命名。

`reset_index()` 把分组索引重新变成普通列。

否则结果会是一个带多层索引的 `Series`，不方便后面做透视表。

月度收益计算后，数据大概是长表结构：

```text
symbol | year | month | monthly_return
159915 | 2023 | 1     | ...
159915 | 2023 | 2     | ...
159915 | 2023 | 3     | ...
```

年度收益计算后：

```text
symbol | year | annual_return
159915 | 2023 | ...
159915 | 2024 | ...
510300 | 2023 | ...
```

## 9. 月度收益透视表

代码：

```python
monthly_return_table = monthly_returns.pivot_table(
    index=["symbol", "year"],
    columns="month",
    values="monthly_return",
)
```

`pivot_table()` 的作用是把“长表”转成“宽表”。

含义：

- `index=["symbol", "year"]`：每一行是一只 ETF 的某一年。
- `columns="month"`：月份变成列。
- `values="monthly_return"`：单元格里放月度收益率。

结果大概是：

```text
symbol  year | 1月    2月    3月    ...   12月
159915  2023 | ...   ...   ...         ...
159915  2024 | ...   ...   ...         ...
510300  2023 | ...   ...   ...         ...
```

## 10. 补齐 1-12 月

```python
monthly_return_table = monthly_return_table.reindex(columns=range(1, 13))
```

`range(1, 13)` 生成：

```text
1, 2, 3, ..., 12
```

`reindex(columns=...)` 的作用是强制表格按 1 到 12 月排列。

如果某个月没有数据，也会保留这个月份列，只是值为空。

## 11. 月份列格式化为两位数字

```python
monthly_return_table.columns = [f"{month:02d}" for month in monthly_return_table.columns]
```

这是列表推导式。

`f"{month:02d}"` 是 f-string 格式化：

- `1` 变成 `"01"`
- `2` 变成 `"02"`
- `12` 还是 `"12"`

最终月份列更整齐：

```text
01, 02, 03, ..., 12
```

## 12. 在月度表中加入年度收益

```python
monthly_return_table["year_return"] = annual_returns.set_index(["symbol", "year"])["annual_return"]
```

这行做了两件事：

1. `annual_returns.set_index(["symbol", "year"])` 把年度收益表设置成和月度收益表一样的索引。
2. `["annual_return"]` 取出年度收益列，赋值到月度表的新列 `year_return`。

pandas 会根据索引自动对齐。

最终月度收益表结构：

```text
symbol year | 01 | 02 | 03 | ... | 12 | year_return
```

## 13. 年度收益表

代码：

```python
annual_return_table = annual_returns.pivot(
    index="year",
    columns="symbol",
    values="annual_return",
)
```

含义：

- `index="year"`：每一行是一年。
- `columns="symbol"`：每只 ETF 变成一列。
- `values="annual_return"`：单元格里放年度收益率。

结果类似：

```text
year | 159915 | 510300 | 511010
2023 | ...    | ...    | ...
2024 | ...    | ...    | ...
```

## 14. `pivot()` 和 `pivot_table()` 的区别

简单理解：

- `pivot()` 要求每个 `index + columns` 组合只能对应一个值。
- `pivot_table()` 可以处理重复组合，并且可以聚合。

这里年度收益已经是唯一组合，所以用 `pivot()` 没问题。

月度收益表用 `pivot_table()` 更稳一些，即使数据里有重复组合，也可以处理。

## 15. 显示为百分比

代码：

```python
display(monthly_return_table.style.format("{:.2%}"))
display(annual_return_table.style.format("{:.2%}"))
```

`display()` 是 Jupyter Notebook 的显示函数。

`.style.format("{:.2%}")` 只是改变显示格式：

- `0.1234` 显示为 `12.34%`
- `-0.0567` 显示为 `-5.67%`

注意：底层数据仍然是小数，不是字符串。

## 16. 最小复习代码

```python
returns_df = df.dropna(subset=["ret"]).copy()
returns_df["year"] = returns_df["date"].dt.year
returns_df["month"] = returns_df["date"].dt.month

monthly_returns = (
    returns_df.groupby(["symbol", "year", "month"])["ret"]
    .apply(lambda ret: (1 + ret).prod() - 1)
    .rename("monthly_return")
    .reset_index()
)

annual_returns = (
    returns_df.groupby(["symbol", "year"])["ret"]
    .apply(lambda ret: (1 + ret).prod() - 1)
    .rename("annual_return")
    .reset_index()
)

monthly_return_table = monthly_returns.pivot_table(
    index=["symbol", "year"],
    columns="month",
    values="monthly_return",
)
monthly_return_table = monthly_return_table.reindex(columns=range(1, 13))
monthly_return_table.columns = [f"{month:02d}" for month in monthly_return_table.columns]
monthly_return_table["year_return"] = annual_returns.set_index(["symbol", "year"])["annual_return"]

annual_return_table = annual_returns.pivot(
    index="year",
    columns="symbol",
    values="annual_return",
)
```

## 17. 常见误区

### 误区 1：把日收益率简单相加

错误写法：

```python
monthly_return = ret.sum()
```

正确写法：

```python
monthly_return = (1 + ret).prod() - 1
```

### 误区 2：忘记按 `symbol` 分组

错误写法：

```python
df["ret"] = df["close"].pct_change()
```

这会把不同 ETF 的价格连起来算收益率。

正确写法：

```python
df["ret"] = df.groupby("symbol")["close"].pct_change()
```

### 误区 3：`date` 还是字符串就用 `.dt`

错误原因：

```python
returns_df["date"].dt.year
```

要求 `date` 是日期类型。

正确前置步骤：

```python
df["date"] = pd.to_datetime(df["date"])
```

### 误区 4：以为 `style.format()` 改了真实数据

```python
monthly_return_table.style.format("{:.2%}")
```

只改变 Notebook 显示效果，不改变底层数值。

