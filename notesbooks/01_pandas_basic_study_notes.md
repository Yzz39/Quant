# Pandas 基础学习笔记

对应 notebook：`notesbooks/01_pandas_basic.ipynb`

对应数据文件：`data/sample_etf_daily.csv`

## 1. 环境和工具关系

这个项目用 `uv` 管理 Python 环境和依赖。

```text
uv
  -> 创建 .venv 虚拟环境
  -> 根据 pyproject.toml 安装 pandas / numpy / matplotlib / jupyter / ipykernel / openpyxl
  -> 根据 uv.lock 锁定具体版本
```

几个包的分工：

| 名称 | 作用 |
|---|---|
| `pandas` | 表格数据分析，核心对象是 `DataFrame` |
| `numpy` | 数值计算基础，pandas 底层会用到 |
| `matplotlib` | 画图，比如净值曲线、价格曲线 |
| `jupyter` | 运行 `.ipynb` notebook |
| `ipykernel` | 让 Jupyter 调用当前 Python 环境执行代码 |
| `openpyxl` | 让 pandas 读写 Excel `.xlsx` 文件 |

## 2. 读取 CSV 数据

当前数据文件路径：

```text
../data/sample_etf_daily.csv
```

因为 notebook 位于 `notesbooks` 目录，所以从 notebook 里读取上一级目录的 `data` 文件夹：

```python
import pandas as pd

df = pd.read_csv("../data/sample_etf_daily.csv", parse_dates=["date"])
```

`parse_dates=["date"]` 的含义是：读取 CSV 时，把 `date` 列解析成日期类型。

注意这里必须写成列表：

```python
parse_dates=["date"]
```

不要写成：

```python
parse_dates="date"
```

否则会报错：

```text
TypeError: Only booleans and lists are accepted for the 'parse_dates' parameter
```

## 3. 当前数据字段

`sample_etf_daily.csv` 包含这些列：

| 列名 | 含义 |
|---|---|
| `date` | 日期 |
| `symbol` | ETF 代码 |
| `name` | ETF 名称 |
| `open` | 开盘价 |
| `high` | 最高价 |
| `low` | 最低价 |
| `close` | 收盘价 |
| `volume` | 成交量 |
| `amount` | 成交额 |

`df.info()` 显示当前数据有 `1566` 行、`9` 列。

## 4. 查看 DataFrame

常用查看方法：

```python
df.head()      # 查看前 5 行
df.tail()      # 查看后 5 行
df.info()      # 查看结构、列类型、缺失值、内存占用
df.describe()  # 查看数值列的统计摘要
df.shape       # 查看行数和列数
df.columns     # 查看列名
df.dtypes      # 查看每列的数据类型
```

`info()` 和 `describe()` 的区别：

| 函数 | 主要用途 |
|---|---|
| `info()` | 看表结构：行数、列数、类型、缺失值 |
| `describe()` | 看统计分布：均值、标准差、最小值、最大值、四分位数 |

Jupyter 里一个代码单元默认只显示最后一行结果。如果要同时看多个结果，用 `display()`：

```python
display(df.head())
display(df.tail())
```

## 5. 选择列和筛选行

选择单列：

```python
df["close"]
```

选择多列：

```python
df[["date", "close", "volume"]]
```

注意多列选择要用双层中括号：

```python
df[["ret", "equity"]]
```

不要写成：

```python
df["ret", "equity"]
```

按条件筛选：

```python
df[df["symbol"] == 510300]
```

多个条件同时筛选：

```python
df[(df["symbol"] == 510300) & (df["close"] > 3.8)]
```

注意每个条件要用括号包起来，条件之间用 `&` 表示“并且”。

当前数据里 `symbol` 的类型是 `int64`，所以筛选时用数字 `510300`。如果写成字符串 `"510300"`，可能筛选不出结果。

## 6. 排序、索引和日期筛选

按日期排序：

```python
df = df.sort_values("date")
```

把 `date` 设置为索引：

```python
df = df.set_index("date")
```

按日期范围筛选：

```python
df.loc["2024-01-01":"2024-03-01"]
```

这句的前提是：`df` 的索引必须是日期索引。

如果 `date` 只是普通列，应该这样筛选：

```python
df[(df["date"] >= "2024-01-01") & (df["date"] <= "2024-03-01")]
```

把索引恢复成普通列：

```python
df = df.reset_index()
```

## 7. 收益率、差值和移动

计算收益率：

```python
df["ret"] = df["close"].pct_change()
```

含义：

```text
ret = 本行 close / 上一行 close - 1
```

计算差值：

```python
df["diff"] = df["close"].diff()
```

含义：

```text
diff = 本行 close - 上一行 close
```

`shift()` 用来移动数据：

```python
df["close"].shift(1)   # 取上一行 close
df["close"].shift(-1)  # 取下一行 close
```

策略收益常见写法：

```python
df["strategy_ret"] = df["signal"].shift(1) * df["ret"]
```

这表示用“上一期信号”乘以“本期收益”。这样做是为了避免用今天收盘后才知道的信号去赚今天的收益。

注意：这句代码要求先有 `signal` 列。

## 8. 缺失值

查看每列缺失值数量：

```python
df.isna().sum()
```

`pct_change()`、`diff()`、`rolling()` 的开头通常会产生缺失值，因为第一行没有上一行，滚动窗口前几行数据也不够。

删除缺失值：

```python
df = df.dropna()
```

填充缺失值为 0：

```python
df = df.fillna(0)
```

用前一个有效值填充：

```python
df = df.ffill()
```

## 9. 滚动计算

20 日均线：

```python
df["ma20"] = df["close"].rolling(20).mean()
```

60 日均线：

```python
df["ma60"] = df["close"].rolling(60).mean()
```

20 日波动率：

```python
df["vol20"] = df["ret"].rolling(20).std()
```

`rolling(20)` 表示每次取最近 20 行作为窗口，再对窗口做统计计算。

## 10. 累计净值

`cumprod()` 表示累计连乘。

计算净值曲线：

```python
df["equity"] = (1 + df["ret"]).cumprod()
```

含义：

```text
每天收益率先变成 1 + ret
然后逐日连乘
得到从起点到当前日期的累计表现
```

例如：

```text
ret = 10%, -5%, 20%
equity = 1.10, 1.045, 1.254
```

## 11. 多个 ETF 要先分组

当前数据里有多个 `symbol`。如果直接做：

```python
df["ret"] = df["close"].pct_change()
```

可能会把不同 ETF 的价格接在一起计算收益率，这是错误的。

更合理的写法是按 `symbol` 分组：

```python
df = df.sort_values(["symbol", "date"])

df["ret"] = df.groupby("symbol")["close"].pct_change()
df["equity"] = (1 + df["ret"]).groupby(df["symbol"]).cumprod()
```

含义：

```text
每个 ETF 单独计算自己的日收益率
每个 ETF 单独计算自己的累计净值
```

如果希望每个 ETF 第一天净值从 `1` 开始：

```python
df["equity"] = (1 + df["ret"]).fillna(1).groupby(df["symbol"]).cumprod()
```

## 12. transform 的理解

`transform()` 的核心是：

```text
按组计算，但结果长度和原表一样
```

计算每个 ETF 自己的 20 日均线：

```python
df["ma20"] = df.groupby("symbol")["close"].transform(
    lambda x: x.rolling(20).mean()
)
```

这里：

```text
groupby("symbol")：按 ETF 代码分组
["close"]：只取收盘价
lambda x：x 是每个 ETF 自己的 close 序列
rolling(20).mean()：计算 20 日均线
transform：把结果按原来的行位置放回 df
```

`transform()` 适合生成新列，比如组内均值、组内排名、组内均线。

## 13. agg 的理解

`agg()` 的核心是：

```text
把多行数据压缩成统计结果
```

例子 1：多列分别用不同统计方法。

```python
summary = df.groupby("symbol").agg({
    "close": "mean",
    "volume": "sum",
    "amount": "sum",
})

display(summary)
```

含义：

```text
每个 ETF：
close 算平均值
volume 算总和
amount 算总和
```

例子 2：单列同时算多个统计指标。

```python
df.groupby("symbol")["close"].agg(["mean", "max", "min", "std"])
```

含义：

```text
每个 ETF 的 close：
算平均值、最大值、最小值、标准差
```

例子 3：多列、多指标一起算。

```python
df.groupby("symbol").agg({
    "close": ["mean", "max", "min", "std"],
    "volume": ["sum", "mean"],
    "amount": ["sum", "mean"],
})
```

`agg()` 和 `transform()` 的区别：

| 函数 | 结果长度 | 适合场景 |
|---|---:|---|
| `agg()` | 每组变成少数几行 | 汇总统计 |
| `transform()` | 和原表一样长 | 生成新列 |

## 14. merge、concat、join

`merge()`：按共同列合并。

```python
price = pd.DataFrame({
    "symbol": ["510300", "159915"],
    "close": [3.8, 2.1],
})

info = pd.DataFrame({
    "symbol": ["510300", "159915"],
    "name": ["沪深300ETF", "创业板ETF"],
})

test = pd.merge(price, info, on="symbol")
```

`concat()`：直接拼接表。

```python
df_all = pd.concat([df_2023, df_2024])       # 上下拼接，增加行
df_new = pd.concat([df_left, df_right], axis=1)  # 左右拼接，增加列
```

`join()`：默认按索引合并。

```python
result = price.set_index("symbol").join(info.set_index("symbol"))
```

简单记法：

```text
merge：按列合并，最常用
concat：直接拼接，上下或左右
join：按索引合并
```

## 15. 今天遇到的常见错误

路径错误：

```python
pd.read_csv("data/sample_etf_daily.csv")
```

如果 notebook 的工作目录是 `notesbooks`，这会去找 `notesbooks/data/sample_etf_daily.csv`，可能找不到。

更适合当前 notebook 的路径：

```python
pd.read_csv("../data/sample_etf_daily.csv", parse_dates=["date"])
```

文件名拼写错误：

```text
sample_eft_daily.csv  # 错
sample_etf_daily.csv  # 对
```

`parse_dates` 参数错误：

```python
parse_dates="date"    # 错
parse_dates=["date"]  # 对
```

把 `groupby` 对象当函数调用：

```python
df.groupby("symbol")(1 + df["ret"]).cumprod()  # 错
```

正确写法：

```python
(1 + df["ret"]).groupby(df["symbol"]).cumprod()
```

多列选择写法错误：

```python
df["ret", "equity"]    # 错
df[["ret", "equity"]]  # 对
```

## 16. 建议复习顺序

1. 先熟悉读取数据和查看数据：`read_csv()`、`head()`、`info()`、`describe()`。
2. 再练习筛选数据：单列、多列、条件筛选、日期筛选。
3. 然后练习收益率：`pct_change()`、`diff()`、`shift()`。
4. 接着练习滚动指标：`rolling()`、`mean()`、`std()`。
5. 最后重点练习分组：`groupby()`、`transform()`、`agg()`。

## 17. 推荐下一步练习

用当前数据完成下面几个小练习：

```python
# 1. 只筛选 510300 的数据
df_510300 = df[df["symbol"] == 510300]

# 2. 给每个 ETF 分别计算 ret、ma20、ma60
df = df.sort_values(["symbol", "date"])
df["ret"] = df.groupby("symbol")["close"].pct_change()
df["ma20"] = df.groupby("symbol")["close"].transform(lambda x: x.rolling(20).mean())
df["ma60"] = df.groupby("symbol")["close"].transform(lambda x: x.rolling(60).mean())

# 3. 汇总每个 ETF 的平均收盘价、总成交量、总成交额
summary = df.groupby("symbol").agg({
    "close": "mean",
    "volume": "sum",
    "amount": "sum",
})

display(summary)
```
