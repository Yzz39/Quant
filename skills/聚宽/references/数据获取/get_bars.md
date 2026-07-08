# get_bars - 获取K线数据

获取证券的K线数据,支持多种频率。

## 函数签名

```python
get_bars(security, count, unit, fields=['open','close','high','low','volume','money'],
         include_now=True, end_dt=None, fq_ref_date=None, df=True)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| count | int | 获取K线的数量 |
| unit | str | K线类型,'1d'/'1m'/'5m'/'15m'/'30m'/'60m'/'1w'/'1M' |
| fields | list | 获取的字段列表 |
| include_now | bool | 是否包含当前K线,默认 True |
| end_dt | str/datetime | 结束时间,默认为当前时间 |
| fq_ref_date | str/datetime | 复权参照日期 |
| df | bool | 是否返回 DataFrame,默认 True |

## 返回值

返回 pandas.DataFrame 或 dict,包含K线数据。

## 支持的K线类型

- **1d**: 日K线
- **1w**: 周K线
- **1M**: 月K线
- **1m**: 1分钟K线
- **5m**: 5分钟K线
- **15m**: 15分钟K线
- **30m**: 30分钟K线
- **60m**: 60分钟K线

## 示例

### 获取日K线

```python
# 获取平安银行最近20天的日K线
df = get_bars('000001.XSHE', 20, '1d',
              fields=['date','open','close','high','low','volume'])
```

### 获取分钟K线

```python
# 获取最近100根1分钟K线
df = get_bars('000001.XSHE', 100, '1m',
              fields=['time','open','close','high','low','volume','money'])

# 获取最近50根5分钟K线
df = get_bars('000001.XSHE', 50, '5m',
              fields=['time','open','close','high','low','volume'])
```

### 获取周K线和月K线

```python
# 获取最近10周周K线
df = get_bars('000001.XSHE', 10, '1w',
              fields=['date','open','close','high','low','volume'])

# 获取最近6个月月K线
df = get_bars('000001.XSHE', 6, '1M',
              fields=['date','open','close','high','low','volume'])
```

## 返回字段说明

| 字段 | 说明 |
|------|------|
| date/time | 时间(日K线为date,分钟K线为time) |
| open | 开盘价 |
| close | 收盘价 |
| high | 最高价 |
| low | 最低价 |
| volume | 成交量 |
| money | 成交额 |

## 注意事项

1. 分钟K线数据在 include_now=True 时包含当前正在形成的K线
2. end_dt 可以指定获取数据的时间范围
3. 返回的数据按时间正序排列
4. 期货K线数据包括持仓量字段

## 相关函数

- [get_price](get_price.md) - 获取行情数据
- [attribute_history](attribute_history.md) - 获取历史数据
