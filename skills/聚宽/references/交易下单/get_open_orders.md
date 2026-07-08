# get_open_orders - 获取未成交订单

获取当前所有未成交的订单。

## 函数签名

```python
get_open_orders()
```

## 返回值

返回 dict,key 为订单ID,value 为 Order 对象。

## 示例

```python
# 获取所有未成交订单
orders = get_open_orders()

for order_id, order in orders.items():
    log.info(f"订单ID: {order_id}")
    log.info(f"证券: {order.security}")
    log.info(f"数量: {order.amount}")
    log.info(f"状态: {order.status}")
```

## 注意事项

1. 只返回未完全成交的订单
2. 已成交或已撤销的订单不返回

## 相关函数

- [get_orders](get_orders.md) - 获取所有订单
- [cancel_order](cancel_order.md) - 撤销订单
