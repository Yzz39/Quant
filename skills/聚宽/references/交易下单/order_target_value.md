# order_target_value - 目标金额下单

调整持仓到目标金额。

## 函数签名

```python
order_target_value(security, value)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| value | float | 目标持仓金额 |

## 返回值

返回 Order 对象。

## 示例

```python
# 调整持仓到10万元
order_target_value('000001.XSHE', 100000)

# 清仓(目标金额为0)
order_target_value('000001.XSHE', 0)

# 等权重配置
total_value = context.portfolio.total_value
target_value = total_value / len(g.stock_pool)
for stock in g.stock_pool:
    order_target_value(stock, target_value)
```

## 注意事项

1. value=0 表示清仓
2. 系统自动计算需要买入或卖出的金额
3. 常用于组合管理和仓位调整

## 相关函数

- [order](order.md) - 按数量下单
- [order_target](order_target.md) - 目标数量下单
- [order_value](order_value.md) - 按金额下单
