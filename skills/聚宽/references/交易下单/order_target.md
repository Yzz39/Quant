# order_target - 目标数量下单

调整持仓到目标数量。

## 函数签名

```python
order_target(security, amount)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| amount | int | 目标持仓数量(股) |

## 返回值

返回 Order 对象。

## 示例

```python
# 清仓
order_target('000001.XSHE', 0)

# 调整到1000股
order_target('000001.XSHE', 1000)

# 卖出部分,保留500股
order_target('000001.XSHE', 500)
```

## 注意事项

1. amount=0 表示清仓
2. 系统会自动计算需要买入或卖出的数量
3. 不考虑资金是否足够

## 相关函数

- [order](order.md) - 按数量下单
- [order_value](order_value.md) - 按金额下单
- [order_target_value](order_target_value.md) - 目标金额下单
