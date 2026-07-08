# get_orders - 查询订单

获取当天的所有订单信息。

## 函数签名

```python
get_orders(order_id=None, security=None, status=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| order_id | str | 订单ID，可选 |
| security | str | 标的代码，可选 |
| status | OrderStatus | 订单状态，可选 |

## 返回值

返回一个 dict，key 是 order_id，value 是 Order 对象。

## OrderStatus 状态

| 状态 | 说明 |
|------|------|
| OrderStatus.new | 订单新创建未委托 |
| OrderStatus.open | 订单未完成，部分或全部未成交 |
| OrderStatus.filled | 订单未完成，部分成交 |
| OrderStatus.canceled | 订单完成，已撤销 |
| OrderStatus.rejected | 订单完成，交易所已拒绝 |
| OrderStatus.held | 订单完成，全部成交 |

## 示例

### 获取所有订单

```python
def after_trading_end(context):
    # 获取当天所有订单
    orders = get_orders()
    for order_id, order in orders.items():
        log.info(f"订单 {order_id}: {order.security}, 状态: {order.status}")
```

### 根据订单ID查询

```python
# 查询特定订单
order = get_orders(order_id='1517627499')
```

### 查询特定标的的订单

```python
# 查询平安银行的所有订单
orders = get_orders(security='000001.XSHE')
```

### 查询特定状态的订单

```python
# 查询所有未完成的订单
orders = get_orders(status=OrderStatus.held)

# 查询所有已撤销的订单
orders = get_orders(status=OrderStatus.canceled)
```

### 组合查询

```python
# 查询平安银行未完成的订单
orders = get_orders(security='000001.XSHE', status=OrderStatus.held)
```

### 订单信息处理

```python
def after_trading_end(context):
    orders = get_orders()

    for order in orders.values():
        # 检查订单状态
        if str(order.status) == 'held':
            log.info(f"已成交: {order.security}, 数量: {order.filled}, 价格: {order.price}")
        elif str(order.status) == 'canceled':
            log.info(f"已撤销: {order.security}")
        else:
            log.info(f"未完成: {order.security}, 状态: {order.status}")
```

## 注意事项

1. 只能查询当天的订单
2. 非交易时间下单，开盘后订单状态会从 new 变为 open
3. new 指订单新创建未委托；open 指已委托未完成
4. 不能保存订单信息到下一个交易日使用

## 相关函数

- [get_trades](get_trades.md) - 获取成交记录
- [cancel_order](../交易下单/cancel_order.md) - 撤单
- [Order](../账户对象/Order.md) - 订单对象
