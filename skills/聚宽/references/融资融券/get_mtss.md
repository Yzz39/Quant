# get_mtss - 获取融资融券数据

获取融资融券余额等数据。

## 函数签名

```python
get_mtss(security, start_date, end_date, fields=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| start_date | str/datetime | 开始日期 |
| end_date | str/datetime | 结束日期 |
| fields | list | 字段列表 |

## 支持字段

- **fin_value**: 融资余额
- **fin_buy_value**: 融资买入额
- **sec_value**: 融券余额
- **sec_sell_value**: 融券卖出额

## 示例

```python
# 获取融资融券数据
mtss = get_mtss('000001.XSHE', '2024-01-01', '2024-01-31',
                fields=['fin_value', 'sec_value'])
```
