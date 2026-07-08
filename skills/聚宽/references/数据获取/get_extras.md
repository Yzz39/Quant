# get_extras - 获取额外数据

获取证券的额外数据,如涨跌幅、换手率等。

## 函数签名

```python
get_extras(symbol, columns, start_date=None, end_date=None, count=None,
           df=True, transform=True)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| symbol | str/list | 证券代码 |
| columns | str/list | 要获取的额外数据字段 |
| start_date | str/datetime | 开始日期 |
| end_date | str/datetime | 结束日期 |
| count | int | 获取数量 |
| df | bool | 是否返回 DataFrame |
| transform | bool | 是否转换格式 |

## 支持的额外数据字段

### 行情指标

- **pre_close**: 昨收价
- **open**: 开盘价
- **high**: 最高价
- **low**: 最低价
- **close**: 收盘价
- **volume**: 成交量
- **money**: 成交额

### 派生指标

- **change**: 涨跌额
- **change_pct**: 涨跌幅
- **turnover**: 换手率
- **turnover_rate**: 换手率(另一种计算方式)

## 示例

### 获取涨跌幅数据

```python
# 获取平安银行最近10天的涨跌幅
df = get_extras('000001.XSHE', ['change_pct'],
                start_date='2024-01-01', end_date='2024-01-15')
```

### 获取换手率数据

```python
# 获取多只股票的换手率
df = get_extras(['000001.XSHE', '000002.XSHE'], ['turnover'],
                count=10)
```

### 获取多个额外字段

```python
# 获取涨跌额和涨跌幅
df = get_extras('000001.XSHE', ['change', 'change_pct'],
                count=20)
```

## 注意事项

1. get_extras 主要用于获取派生指标
2. 基础行情数据建议使用 get_price 或 attribute_history
3. 换手率数据需要足够的历史数据支持

## 相关函数

- [get_price](get_price.md) - 获取基础行情数据
- [attribute_history](attribute_history.md) - 获取历史数据
