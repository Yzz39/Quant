# Position - 持仓对象

表示单个证券的持仓信息。

## 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| amount | float | 总持仓数量 |
| avg_cost | float | 平均成本价 |
| transaction_cost | float | 交易费用 |
| total_amount | float | 历史总持仓量 |
| closeable_amount | float | 可卖数量(T+1) |
| value | float | 持仓市值 |
| pnl_daily | float | 当日盈亏 |
| pnl | float | 总盈亏 |

## 示例

```python
def handle_data(context, data):
    security = '000001.XSHE'
    
    # 获取持仓对象
    position = context.portfolio.positions[security]
    
    # 获取持仓数量
    amount = position.amount
    
    # 获取可卖数量
    closeable = position.closeable_amount
    
    # 获取持仓市值
    value = position.value
    
    # 获取平均成本
    avg_cost = position.avg_cost
    
    # 计算盈亏
    current_price = get_price(security, end_date=context.current_dt, count=1, fields='close')
    profit = (current_price - avg_cost) * amount
    
    log.info(f"持仓数量: {amount}")
    log.info(f"可卖数量: {closeable}")
    log.info(f"持仓市值: {value}")
    log.info(f"浮动盈亏: {profit}")
```

## T+1 规则

- **amount**: 总持仓数量
- **closeable_amount**: 可卖数量(今买部分不可卖)
- 当天买入的股票当天不能卖出

## 注意事项

1. 检查持仓前应先确认持仓存在
2. 使用 closeable_amount 判断可卖数量
3. avg_cost 是按复权价格计算的成本

## 相关对象

- [Portfolio](Portfolio.md) - 账户对象
- [Order](Order.md) - 订单对象
