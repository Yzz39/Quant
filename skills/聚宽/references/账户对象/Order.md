# Order - 订单对象

表示一个订单的信息。

## 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| order_id | str | 订单ID |
| security | str | 证券代码 |
| action | str | 订单类型('buy'/'sell') |
| amount | float | 委托数量 |
| price | float | 委托价格 |
| filled | float | 已成交数量 |
| status | str | 订单状态 |
| dt | datetime | 订单时间 |

## 订单状态

- **Order.Status.SUBMITTED**: 已提交
- **Order.Status.FILLED**: 已成交
- **Order.Status.CANCELLED**: 已撤销
- **Order.Status.REJECTED**: 已拒绝

## 示例

```python
# 下单并获取订单对象
order = order('000001.XSHE', 1000)

# 查看订单信息
log.info(f"订单ID: {order.order_id}")
log.info(f"证券: {order.security}")
log.info(f"数量: {order.amount}")
log.info(f"状态: {order.status}")

# 检查订单是否成交
if order.status == Order.Status.FILLED:
    log.info("订单已成交")
```

## 注意事项

1. 订单提交后会立即返回Order对象
2. 订单状态会实时更新
3. 市价单可能部分成交

## 相关对象

- [Trade](Trade.md) - 成交对象
- [Position](Position.md) - 持仓对象
