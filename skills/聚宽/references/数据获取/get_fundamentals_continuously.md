# get_fundamentals_continuously - 查询多日财务数据

查询多个日期的财务数据，返回 Panel 或 DataFrame 格式。

## 函数签名

```python
get_fundamentals_continuously(query_object, end_date=None, count=None, panel=True)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| query_object | Query | sqlalchemy.orm.query.Query 对象 |
| end_date | str/datetime | 查询结束日期 |
| count | int | 获取 end_date 前 count 个日期的数据 |
| panel | bool | 是否返回 Panel（建议设为 False 返回 DataFrame） |

## 返回值

- **panel=True**: 返回 pandas.Panel（已废弃，pandas 0.24+ 移除）
- **panel=False**: 返回等效的 DataFrame

**注意**: 出于性能考虑，返回总条数不超过 5000 条（股票数量 × count < 5000）。

## 示例

### 基本查询（返回 Panel）

```python
q = query(
    valuation.turnover_ratio,
    valuation.market_cap,
    indicator.eps
).filter(valuation.code.in_(['000001.XSHE', '600000.XSHG']))

panel = get_fundamentals_continuously(q, end_date='2018-01-01', count=5)
```

### 返回 DataFrame（推荐）

```python
# 建议设置 panel=False
df = get_fundamentals_continuously(
    q,
    end_date='2018-01-01',
    count=5,
    panel=False
)
```

### Panel 数据访问

```python
# 按股票访问
df = panel.minor_xs('600000.XSHG')

# 按日期访问
df = panel.major_xs('2017-12-25')

# 按字段访问
df = panel.xs('turnover_ratio', axis=0)
```

### 实际应用

```python
def initialize(context):
    g.stocks = ['000001.XSHE', '000002.XSHE', '600000.XSHG']
    run_daily(rebalance, time='open')

def rebalance(context):
    # 获取过去5天的数据
    q = query(
        valuation.code,
        valuation.turnover_ratio,
        valuation.market_cap
    ).filter(valuation.code.in_(g.stocks))

    df = get_fundamentals_continuously(
        q,
        end_date=context.previous_date,
        count=5,
        panel=False
    )

    # 分析数据
    log.info(df)
```

## 数据结构

### Panel 结构（已废弃）

```
Dimensions: 3 (items) x 5 (major_axis) x 2 (minor_axis)
Items axis: turnover_ratio to eps (字段)
Major_axis axis: 2017-12-25 to 2017-12-29 (日期)
Minor_axis axis: 000001.XSHE to 600000.XSHG (股票)
```

### DataFrame 结构（推荐）

```
index: 日期
columns: MultiIndex (股票代码, 字段)
```

## 使用场景

### 时间序列分析

```python
# 获取某只股票的历史市值数据
q = query(valuation).filter(valuation.code == '000001.XSHE')
panel = get_fundamentals_continuously(q, end_date='2018-01-01', count=20)

# 分析市值变化趋势
market_caps = panel['market_cap']
```

### 多指标对比

```python
# 获取多个指标的历史数据
q = query(
    valuation.market_cap,
    valuation.pe_ratio,
    valuation.pb_ratio,
    indicator.roe
).filter(valuation.code == '000001.XSHE')

df = get_fundamentals_continuously(q, count=10, panel=False)
```

### 股票池分析

```python
# 分析股票池的历史数据
stocks = get_index_stocks('000300.XSHG')[:10]  # 取10只股票

q = query(
    valuation.code,
    valuation.market_cap,
    indicator.eps
).filter(valuation.code.in_(stocks))

df = get_fundamentals_continuously(q, count=5, panel=False)
```

## 注意事项

1. **性能限制**: 股票数量 × count < 5000
2. **Panel 废弃**: pandas 0.24+ 已移除 Panel，建议使用 panel=False
3. **数据完整性**: 停牌期间数据可能缺失
4. **内存占用**: 大量数据会占用较多内存

## 相关函数

- [get_fundamentals](get_fundamentals.md) - 查询单日财务数据
- [get_history_fundamentals](get_history_fundamentals.md) - 获取历史财务数据
- [get_price](get_price.md) - 获取行情数据
