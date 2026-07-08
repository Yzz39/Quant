# get_valuation - 获取市值数据

获取多个标的在指定交易日范围内的市值表数据。

## 函数签名

```python
get_valuation(security, start_date=None, end_date=None, fields=None, count=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str/list | 标的代码（单个或列表） |
| start_date | str | 查询开始日期（不能与 count 共用） |
| end_date | str | 查询结束日期 |
| fields | list | 市值表字段列表 |
| count | int | 往前查询每个标的 count 个交易日 |

## 返回值

返回 DataFrame，索引为整数索引，结果中总会包含 code、day 字段。

## 可用字段

| 字段 | 说明 |
|------|------|
| code | 股票代码（带后缀） |
| day | 日期 |
| capitalization | 总股本(万股) |
| circulating_cap | 流通股本(万股) |
| market_cap | 总市值(亿元) |
| circulating_market_cap | 流通市值(亿元) |
| turnover_ratio | 换手率(%) |
| pe_ratio | 市盈率(PE, TTM) |
| pe_ratio_lyr | 市盈率(PE) |
| pb_ratio | 市净率(PB) |
| ps_ratio | 市销率(PS, TTM) |
| pcf_ratio | 市现率(PCF) |

## 示例

### 查询单个标的

```python
# 查询平安银行最近3天的市值数据
df = get_valuation(
    '000001.XSHE',
    end_date='2019-11-18',
    count=3,
    fields=['capitalization', 'market_cap']
)
```

### 查询多个标的

```python
# 查询多只股票的市值数据
df = get_valuation(
    ['000001.XSHE', '000002.XSHE', '600000.XSHG'],
    end_date='2019-11-18',
    count=5,
    fields=['market_cap', 'pe_ratio', 'pb_ratio']
)
```

### 指定时间范围

```python
# 查询指定时间范围的数据
df = get_valuation(
    ['000001.XSHE', '600000.XSHG'],
    start_date='2019-11-01',
    end_date='2019-11-18',
    fields=['capitalization', 'market_cap', 'turnover_ratio']
)
```

### 查询所有字段

```python
# 不指定 fields，返回所有字段
df = get_valuation('000001.XSHE', end_date='2019-11-18', count=1)
```

### 策略中的应用

```python
def initialize(context):
    g.stocks = ['000001.XSHE', '000002.XSHE', '600000.XSHG']
    run_daily(rebalance, time='open')

def rebalance(context, data):
    # 获取最新的市值数据
    df = get_valuation(
        g.stocks,
        end_date=context.previous_date,
        count=1,
        fields=['market_cap', 'pe_ratio', 'pb_ratio']
    )

    # 筛选低估值股票
    filtered = df[
        (df['pe_ratio'] > 0) &
        (df['pe_ratio'] < 20) &
        (df['pb_ratio'] > 0) &
        (df['pb_ratio'] < 3)
    ]

    log.info(f"低估值股票: {filtered['code'].tolist()}")
```

### 市值分析

```python
# 获取历史市值数据并分析
df = get_valuation(
    '000001.XSHE',
    start_date='2019-10-01',
    end_date='2019-11-18',
    fields=['market_cap', 'pe_ratio', 'turnover_ratio']
)

# 计算平均市值
avg_market_cap = df['market_cap'].mean()

# 查找最大市值
max_cap_date = df.loc[df['market_cap'].idxmax(), 'day']
max_cap_value = df['market_cap'].max()

log.info(f"平均市值: {avg_market_cap:.2f} 亿元")
log.info(f"最大市值日期: {max_cap_date}, 值: {max_cap_value:.2f} 亿元")
```

### 换手率分析

```python
# 获取换手率数据
df = get_valuation(
    ['000001.XSHE', '600000.XSHG'],
    end_date='2019-11-18',
    count=10,
    fields=['turnover_ratio']
)

# 计算平均换手率
avg_turnover = df.groupby('code')['turnover_ratio'].mean()
log.info(f"平均换手率:\n{avg_turnover}")
```

## 注意事项

1. **数据限制**: 每次最多返回 5000 条数据
2. **不要查询当天数据**: PE/市值等依赖收盘价的指标是盘后更新的
3. **停牌处理**: 停牌期间换手率为 0
4. **count 限制**: 如果标的停牌，返回数量可能少于 count
5. **参数互斥**: start_date 和 count 不能同时使用

## 字段说明

### 市值相关

- **capitalization**: 总股本，包含 A 股、B 股和 H 股
- **circulating_cap**: 流通股本，A 股市场的流通股本
- **market_cap**: 总市值 = 收盘价 × 总股本
- **circulating_market_cap**: 流通市值 = 收盘价 × 流通股本

### 估值指标

- **pe_ratio**: 市盈率 TTM，滚动 12 个月市盈率
- **pe_ratio_lyr**: 静态市盈率，以上一年度 EPS 计算
- **pb_ratio**: 市净率 = 股价 / 每股净资产
- **ps_ratio**: 市销率 TTM
- **pcf_ratio**: 市现率 TTM

### 其他

- **turnover_ratio**: 换手率 = 成交量 / 流通股本 × 100%

## 相关函数

- [get_fundamentals](get_fundamentals.md) - 查询所有财务数据
- [get_fundamentals_continuously](get_fundamentals_continuously.md) - 查询多日财务数据
- [get_price](get_price.md) - 获取行情数据
