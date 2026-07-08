# attribute_history - 获取历史属性数据

获取一只或者多只证券的历史属性数据，返回 DataFrame 格式。

## 函数签名

```python
attribute_history(security, count, unit, fields, df=True, skip_paused=True, fq='pre')
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str/list | 一只证券代码或证券代码列表 |
| count | int | 数量，获取过去 count 个单位时间的数据 |
| unit | str | 单位时间，支持 '1d'/'1w'/'1m' 等 |
| fields | str/list | 字段名，如 'open'/'close'/'high'/'low'/'volume'/'money' 等 |
| df | bool | 是否返回 DataFrame，True 返回 DataFrame，False 返回 dict |
| skip_paused | bool | 是否跳过停牌日期，默认 True |
| fq | str | 复权方式，'pre' 前复权，'none' 不复权 |

## 返回值

- **df=True**: 返回 pandas.DataFrame，索引为日期，列为字段
- **df=False**: 返回 dict，key 为字段，value 为 numpy.ndarray

## 示例

### 获取单只股票数据（DataFrame）

```python
# 获取平安银行过去5天的收盘价
df = attribute_history('000001.XSHE', 5, '1d', ['close'])
# 返回 DataFrame，索引为日期，列为 'close'

# 获取多字段
df = attribute_history('000001.XSHE', 5, '1d', ['open', 'close', 'high', 'low'])
# 返回多列 DataFrame
```

### 获取单只股票数据（dict）

```python
# 返回 dict 格式
data = attribute_history('000001.XSHE', 5, '1d', ['close'], df=False)

# 访问数据
close_prices = data['close']  # numpy array
latest_close = close_prices[-1]  # 最新收盘价
```

### 获取多只股票数据

```python
# 获取多只股票的数据
df = attribute_history(['000001.XSHE', '000002.XSHE'], 5, '1d', ['close'])

# df 是一个 MultiIndex DataFrame
```

### 计算均线

```python
# 获取过去20天的收盘价
df = attribute_history('000001.XSHE', 20, '1d', ['close'])

# 计算5日均线
MA5 = df['close'][:5].mean()

# 计算20日均线
MA20 = df['close'].mean()
```

### 获取分钟数据

```python
# 获取过去100分钟的收盘价
df = attribute_history('000001.XSHE', 100, '1m', ['close', 'volume'])
```

### 实际应用

```python
def handle_data(context, data):
    security = g.security

    # 获取历史数据
    hist = attribute_history(security, 20, '1d', ['open', 'close', 'high', 'low', 'volume'])

    # 计算指标
    MA5 = hist['close'][:5].mean()
    MA20 = hist['close'].mean()
    current_price = hist['close'][-1]

    # 交易逻辑
    if MA5 > MA20 and current_price > MA5:
        # 买入
        order_value(security, context.portfolio.available_cash)
```

## 与 get_price 的区别

| 特性 | attribute_history | get_price |
|------|-------------------|-----------|
| 返回格式 | DataFrame/dict | DataFrame |
| 索引 | 日期索引 | 证券代码列 |
| 使用场景 | 策略中计算指标 | 数据分析 |
| 复权方式 | 默认前复权 | 可选复权方式 |
| 时间参数 | count + unit | end_date + count |

## 注意事项

1. **停牌处理**: skip_paused=True 时会跳过停牌日期
2. **数据顺序**: 返回的数据按时间倒序，最新的在最后
3. **索引访问**: df['close'][-1] 是最新数据，df['close'][0] 是最旧数据
4. **复权影响**: 默认前复权，价格可能与实际价格不同

## 常用字段

### 价格字段

- **open**: 开盘价
- **close**: 收盘价
- **high**: 最高价
- **low**: 最低价
- **avg**: 均价

### 成交量字段

- **volume**: 成交量
- **money**: 成交额

### 其他字段

- **high_limit**: 涨停价
- **low_limit**: 跌停价
- **factor**: 复权因子

## 相关函数

- [get_price](get_price.md) - 获取行情数据
- [history](history.md) - 获取多个证券数据
- [get_current_data](get_current_data.md) - 获取当前数据
