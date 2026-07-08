# get_billboard_list - 获取龙虎榜数据

获取沪深龙虎榜数据。

## 函数签名

```python
get_billboard_list(stock=None, start_date=None, end_date=None, count=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| stock | str | 股票代码 |
| start_date | str/datetime | 开始日期 |
| end_date | str/datetime | 结束日期 |
| count | int | 返回多少条记录 |

## 返回值

返回 pandas.DataFrame,包含龙虎榜数据。

## 示例

```python
# 获取最近一天的龙虎榜
billboard = get_billboard_list(count=1)

# 获取特定股票的龙虎榜
billboard = get_billboard_list(stock='000001.XSHE', start_date='2024-01-01', end_date='2024-01-31')
```

## 注意事项

1. 龙虎榜数据每日更新
2. 包含涨跌幅异常、换手率异常等上榜股票

## 相关函数

- [get_price](get_price.md) - 获取行情数据
