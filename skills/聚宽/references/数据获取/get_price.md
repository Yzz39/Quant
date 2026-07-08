# get_price - 获取历史行情数据

获取一只或者多只证券的历史行情数据。

## 函数签名

```python
get_price(security, end_date=None, count=None, frequency='1d', fields=None, fq='pre')
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str/list | 一只证券代码或者一个证券代码的 list |
| end_date | str/datetime | 结束日期，默认为当前日期 |
| count | int | 数量，表示返回 end_date 之前 count 个交易日的数据 |
| frequency | str | 数据频率，支持 '1d'/'1w'/'1m' 等 |
| fields | str/list | 字段名，如 'open'/'close'/'high'/'low'/'volume'/'money' 等 |
| fq | str | 复权方式，'pre' 前复权，'none' 不复权，'post' 后复权 |

## 返回值

返回一个 pandas.DataFrame 对象，索引为日期，列为证券代码。

## 示例

### 获取单只股票数据

```python
# 获取平安银行最近5天的收盘价
df = get_price('000001.XSHE', end_date='2024-01-15', count=5, fields='close')
```

### 获取多只股票数据

```python
# 获取多只股票的开高低收数据
df = get_price(['000001.XSHE', '000002.XSHE'], end_date='2024-01-15', count=10,
               fields=['open', 'close', 'high', 'low'])
```

### 获取分钟数据

```python
# 获取分钟级数据
df = get_price('000001.XSHE', end_date='2024-01-15 14:00:00', count=100,
               frequency='1m', fields='close')
```

### 获取期货数据

```python
# 获取期货合约数据
df = get_price('IF2401.CCFX', end_date='2024-01-15 15:00:00', count=5,
               fields=['close', 'open_interest'])
```

## 注意事项

1. end_date 和 count 参数至少提供一个
2. 返回的数据已经按照指定复权方式处理
3. 期货数据包含持仓量字段 'open_interest'
4. 分钟数据需要指定具体时间点

## 相关函数

- [history](history.md) - 获取多个证券的历史数据
- [attribute_history](attribute_history.md) - 获取历史属性数据
- [get_current_data](get_current_data.md) - 获取当前数据
