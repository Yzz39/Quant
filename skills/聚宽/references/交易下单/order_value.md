# order_value - 按金额下单

指定买入或卖出金额进行交易。

## 函数签名

```python
order_value(security, value)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| value | float | 交易金额,正数买入,负数卖出 |

## 返回值

返回 Order 对象。

## 示例

```python
# 买入10万元
order_value('000001.XSHE', 100000)

# 卖出5万元
order_value('000001.XSHE', -50000)

# 使用所有可用资金买入
cash = context.portfolio.available_cash
order_value('000001.XSHE', cash)
```

## 注意事项

1. value>0 买入,value<0 卖出
2. 买入时金额不能超过可用资金
3. 卖出时金额不能超过持仓市值

## 相关函数

- [order](order.md) - 按数量下单
- [order_target](order_target.md) - 目标数量下单
- [order_target_value](order_target_value.md) - 目标金额下单
