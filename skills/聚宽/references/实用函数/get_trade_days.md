# get_trade_days - 获取交易日

获取指定时间范围内的交易日列表。

## 函数签名

```python
get_trade_days(start_date, end_date)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| start_date | str/datetime | 开始日期 |
| end_date | str/datetime | 结束日期 |

## 返回值

返回 pandas.DatetimeIndex,包含交易日列表。

## 示例

```python
# 获取2024年1月的交易日
days = get_trade_days('2024-01-01', '2024-01-31')
print(len(days))  # 交易日数量
print(days)  # 交易日列表

# 判断是否为交易日
today = datetime.datetime.now().date()
if today in get_trade_days(today, today):
    print("今天是交易日")
```

## 注意事项

1. 只返回交易日,排除周末和节假日
2. 包含start_date和end_date
3. 返回的是DatetimeIndex对象

## 常见用途

1. 计算交易日数量
2. 判断是否为交易日
3. 遍历交易日
