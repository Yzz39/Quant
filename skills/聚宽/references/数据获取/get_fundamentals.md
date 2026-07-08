# get_fundamentals - 查询财务数据

查询股票的市值数据、资产负债数据、现金流数据、利润数据、财务指标数据。

## 函数签名

```python
get_fundamentals(query_object, date=None, statDate=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| query_object | Query | sqlalchemy.orm.query.Query 对象 |
| date | str/datetime | 查询日期，默认为昨天 |
| statDate | str | 财报统计的季度或年份，如 '2015q1', '2015' |

## 注意事项

- **date 和 statDate 只能传一个**
- **date 参数**: 查询指定日期收盘后能看到的最近数据，不会有未来函数
- **statDate 参数**: 查询指定季度/年份的财务数据，可能有未来函数
- **默认值**: 回测模块默认为 context.current_dt 前一天，研究模块为昨天

## 返回值

返回 pandas.DataFrame，每一行对应数据库返回的一行。

## 可查询的数据表

### valuation - 市值数据

每天更新，包含股本、市值、市盈率、市净率等。

```python
q = query(valuation).filter(valuation.code == '000001.XSHE')
df = get_fundamentals(q, '2015-10-15')
```

### balance - 资产负债数据

按季度更新，包含资产、负债、股东权益等。

```python
q = query(balance).filter(balance.code == '000001.XSHE')
df = get_fundamentals(q, statDate='2015q3')
```

### cash_flow - 现金流数据

按季度更新，包含经营、投资、筹资现金流。

```python
q = query(cash_flow).filter(cash_flow.code == '000001.XSHE')
df = get_fundamentals(q, statDate='2015q3')
```

### income - 利润数据

按季度更新，包含营业收入、净利润等。

```python
q = query(income).filter(income.code == '000001.XSHE')
df = get_fundamentals(q, statDate='2015q3')
```

### indicator - 财务指标数据

按季度更新，包含 ROE、ROA、毛利率等。

```python
q = query(indicator).filter(indicator.code == '000001.XSHE')
df = get_fundamentals(q, statDate='2015q3')
```

## 示例

### 基本查询

```python
# 查询平安银行的所有市值数据
q = query(valuation).filter(valuation.code == '000001.XSHE')
df = get_fundamentals(q, '2015-10-15')
log.info(df['market_cap'][0])  # 打印总市值
```

### 多股票查询

```python
# 获取多只股票的市值和利润
df = get_fundamentals(query(
    valuation, income
).filter(
    valuation.code.in_(['000001.XSHE', '600000.XSHG'])
), date='2015-10-15')
```

### 条件筛选

```python
# 选出总市值>1000亿，市盈率<10，营业收入>200亿的股票
df = get_fundamentals(query(
    valuation.code,
    valuation.market_cap,
    valuation.pe_ratio,
    income.total_operating_revenue
).filter(
    valuation.market_cap > 1000,
    valuation.pe_ratio < 10,
    income.total_operating_revenue > 2e10
).order_by(
    valuation.market_cap.desc()
).limit(100), date='2015-10-15')
```

### 使用 or_ 条件

```python
from sqlalchemy.sql.expression import or_

# 查询市值>1000亿 或者 市盈率<10的股票
df = get_fundamentals(query(
    valuation.code
).filter(
    or_(
        valuation.market_cap > 1000,
        valuation.pe_ratio < 10
    )
))
```

### 查询季度数据

```python
# 查询平安银行2014年四个季度的季报
q = query(
    income.statDate,
    income.code,
    income.basic_eps,
    balance.cash_equivalents
).filter(income.code == '000001.XSHE')

rets = [get_fundamentals(q, statDate='2014q'+str(i)) for i in range(1, 5)]

# 查询2014年年报
ret = get_fundamentals(q, statDate='2014')
```

## 常用字段

### 市值数据 (valuation)

- **market_cap**: 总市值(亿元)
- **circulating_market_cap**: 流通市值(亿元)
- **pe_ratio**: 市盈率(TTM)
- **pb_ratio**: 市净率
- **turnover_ratio**: 换手率(%)
- **capitalization**: 总股本(万股)
- **circulating_cap**: 流通股本(万股)

### 资产负债 (balance)

- **total_assets**: 资产总计
- **total_liability**: 负债合计
- **total_owner_equities**: 股东权益合计
- **cash_equivalents**: 货币资金
- **fixed_assets**: 固定资产
- **total_current_assets**: 流动资产合计

### 利润数据 (income)

- **total_operating_revenue**: 营业总收入
- **operating_revenue**: 营业收入
- **operating_profit**: 营业利润
- **total_profit**: 利润总额
- **net_profit**: 净利润
- **basic_eps**: 基本每股收益

### 现金流数据 (cash_flow)

- **net_operate_cash_flow**: 经营活动现金流量净额
- **net_invest_cash_flow**: 投资活动现金流量净额
- **net_finance_cash_flow**: 筹资活动现金流量净额

### 财务指标 (indicator)

- **roe**: 净资产收益率(%)
- **roa**: 总资产净利率(%)
- **gross_profit_margin**: 销售毛利率(%)
- **net_profit_margin**: 销售净利率(%)
- **eps**: 每股收益(元)

## 注意事项

1. **数据限制**: 每次最多返回 5000 行
2. **未来函数**: 使用 statDate 时要注意未来函数风险
3. **银行业专项数据**: 只有年报数据，需传 statDate 参数
4. **估值表**: 不要查询当天数据，盘后更新

## 相关函数

- [get_fundamentals_continuously](get_fundamentals_continuously.md) - 查询多日财务数据
- [get_history_fundamentals](get_history_fundamentals.md) - 获取历史财务数据
- [get_valuation](get_valuation.md) - 获取市值数据
- [财务数据表说明](财务数据表说明.md) - 详细字段说明
