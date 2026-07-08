# batch_submit_orders - 批量下单

批量提交多个订单。

## 函数签名

```python
batch_submit_orders(order_list)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| order_list | list | 订单列表,每个元素是 (security, amount) 或 (security, amount, style) |

## 返回值

返回 Order 对象列表。

## 示例

```python
# 批量买入
orders = batch_submit_orders([
    ('000001.XSHE', 1000),
    ('000002.XSHE', 1000),
    ('600000.XSHG', 1000)
])

# 批量卖出
orders = batch_submit_orders([
    ('000001.XSHE', -500),
    ('000002.XSHE', -500)
])
```

## 注意事项

1. 批量下单可以提高效率
2. 所有订单同时提交
3. 返回的订单列表与输入顺序对应

## 相关函数

- [order](order.md) - 单个下单
- [batch_cancel_orders](batch_cancel_orders.md) - 批量撤单
