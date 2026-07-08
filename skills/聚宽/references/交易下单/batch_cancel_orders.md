# batch_cancel_orders - 批量撤单

批量撤销多个订单。

## 函数签名

```python
batch_cancel_orders(order_list)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| order_list | list | 订单对象列表 |

## 示例

```python
# 获取所有未成交订单
open_orders = get_open_orders()

# 批量撤销
if open_orders:
    batch_cancel_orders(list(open_orders.values()))
```

## 注意事项

1. 只能撤销未成交的订单
2. 已成交的订单无法撤销

## 相关函数

- [cancel_order](cancel_order.md) - 撤销单个订单
- [get_open_orders](get_open_orders.md) - 获取未成交订单
