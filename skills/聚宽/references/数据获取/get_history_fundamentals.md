# get_history_fundamentals - 获取历史财务数据

获取多个季度/年度的三大财务报表和财务指标数据。

## 函数签名

```python
get_history_fundamentals(security, fields, watch_date=None, stat_date=None, count=1, interval='1q', stat_by_year=False)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str/list | 股票代码或代码列表 |
| fields | list | 要查询的财务数据字段列表 |
| watch_date | str/datetime | 观察日期（与 stat_date 二选一） |
| stat_date | str | 统计日期（与 watch_date 二选一） |
| count | int | 查询的报告期数量，默认 1 |
| interval | str | 报告期间隔，'1q' 或 '1y' |
| stat_by_year | bool | 是否返回年度数据 |

## 参数说明

### watch_date vs stat_date

- **watch_date**: 返回该日期前发布的报表数据
- **stat_date**: 返回该报告期及之前的历史数据
- **两者只能指定一个**

### interval 说明

- **'1q'**: 间隔一季度
  - stat_date='2019q1', count=4 → 返回 2018q2, 2018q3, 2018q4, 2019q1
- **'1y'**: 间隔一年
  - stat_date='2019q1', count=4 → 返回 2016q1, 2017q1, 2018q1, 2019q1

### stat_by_year 说明

- **False** (默认): 返回季度数据
  - interval 可以是 '1q' 或 '1y'
  - stat_date 可以是 '2019q1' 格式
  - fields 只能选择 balance/income/cash_flow/indicator
- **True**: 返回年度数据
  - interval 必须是 '1y'
  - stat_date 必须是年份（如 2019, '2019'）
  - fields 可选择所有表（包括银行、保险专项数据）

## 返回值

返回 pandas.DataFrame，每个股票每个报告期占用一行。

**注意**:
- 每次最多返回 50000 条数据
- 不支持 valuation 市值表

## 示例

### 基本查询

```python
# 查询单只股票的多个季度数据
security = ['000001.XSHE']
fields = [balance.cash_equivalents, income.total_operating_revenue]

df = get_history_fundamentals(
    security,
    fields,
    stat_date='2019q1',
    count=5,
    interval='1q'
)
```

### 多股票查询

```python
# 查询多只股票
security = ['000001.XSHE', '600000.XSHG']
fields = [
    balance.cash_equivalents,
    cash_flow.net_deposit_increase,
    income.total_operating_revenue
]

df = get_history_fundamentals(
    security,
    fields,
    stat_date='2019q1',
    count=5,
    interval='1q'
)

# 按股票分组分析
print(df.groupby('code').mean())
```

### 使用 watch_date

```python
# 获取观察日期之前的数据
df = get_history_fundamentals(
    '000001.XSHE',
    [income.net_profit, indicator.roe],
    watch_date='2019-03-31',
    count=4
)
```

### 年度数据查询

```python
# 查询年度数据
df = get_history_fundamentals(
    '000001.XSHE',
    [income.net_profit, indicator.roe],
    stat_date='2018',
    count=5,
    interval='1y',
    stat_by_year=True
)
```

### 间隔一年查询

```python
# 每年同期数据
df = get_history_fundamentals(
    '000001.XSHE',
    [income.total_operating_revenue],
    stat_date='2019q1',
    count=4,
    interval='1y'
)
# 返回 2016q1, 2017q1, 2018q1, 2019q1
```

### 策略中的应用

```python
def initialize(context):
    g.stock = '000001.XSHE'
    run_daily(analyze, time='open')

def analyze(context, data):
    # 获取过去4个季度的净利润
    df = get_history_fundamentals(
        g.stock,
        [income.net_profit, income.statDate],
        stat_date=context.current_dt.strftime('%Yq%m'),
        count=4,
        interval='1q'
    )

    # 计算净利润增长率
    profits = df['net_profit'].values
    if len(profits) >= 2:
        growth_rate = (profits[-1] - profits[-2]) / profits[-2]
        log.info(f"净利润增长率: {growth_rate:.2%}")
```

## 常用字段组合

### 资产负债表字段

```python
fields = [
    balance.total_assets,           # 总资产
    balance.total_liability,        # 总负债
    balance.total_owner_equities,   # 股东权益
    balance.cash_equivalents        # 货币资金
]
```

### 利润表字段

```python
fields = [
    income.total_operating_revenue,  # 营业总收入
    income.operating_profit,         # 营业利润
    income.net_profit,               # 净利润
    income.basic_eps                 # 每股收益
]
```

### 现金流表字段

```python
fields = [
    cash_flow.net_operate_cash_flow,   # 经营现金流
    cash_flow.net_invest_cash_flow,    # 投资现金流
    cash_flow.net_finance_cash_flow    # 筹资现金流
]
```

### 财务指标字段

```python
fields = [
    indicator.roe,                    # 净资产收益率
    indicator.roa,                    # 总资产净利率
    indicator.gross_profit_margin,    # 毛利率
    indicator.net_profit_margin,      # 净利率
    indicator.eps                     # 每股收益
]
```

## 注意事项

1. **数据限制**: 每次最多返回 50000 条
2. **未来函数**: 使用 statDate 时要注意避免未来函数
3. **缺失数据**: 某些报告期数据可能缺失
4. **时间范围**: count 过大会包含很早的数据

## 相关函数

- [get_fundamentals](get_fundamentals.md) - 查询单日财务数据
- [get_fundamentals_continuously](get_fundamentals_continuously.md) - 查询多日数据
- [财务数据表说明](财务数据表说明.md) - 详细字段说明
