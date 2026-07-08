# cancel_order - 撤销订单

撤销指定的订单。

## 函数签名

```python
cancel_order(order)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| order | Order/str | 订单对象或订单ID |

## 示例

```python
# 方式1: 使用订单对象
order = order('000001.XSHE', 1000)
cancel_order(order)

# 方式2: 使用订单ID
orders = get_open_orders()
for order_id in orders:
    cancel_order(order_id)
```

## 注意事项

1. 只能撤销未完全成交的订单
2. 已成交的部分无法撤销

## 相关函数

- [batch_cancel_orders](batch_cancel_orders.md) - 批量撤单
- [get_open_orders](get_open_orders.md) - 获取未成交订单
