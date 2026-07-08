# Trade - 成交对象

表示一笔成交记录。

## 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| price | float | 成交价格 |
| amount | float | 成交数量 |
| money | float | 成交金额 |
| side | str | 买卖方向('buy'/'sell') |
| dt | datetime | 成交时间 |
| order_id | str | 订单ID |

## 示例

```python
def after_trading_end(context):
    # 获取当日所有成交记录
    trades = get_trades()
    
    for trade_id, trade in trades.items():
        log.info(f"证券: {trade.security}")
        log.info(f"方向: {trade.side}")
        log.info(f"价格: {trade.price}")
        log.info(f"数量: {trade.amount}")
        log.info(f"金额: {trade.money}")
        log.info(f"时间: {trade.dt}")
```

## 注意事项

1. 一个订单可能产生多笔成交
2. Trade对象记录每笔实际成交
3. 通过get_trades()获取所有成交

## 相关对象

- [Order](Order.md) - 订单对象
- [Position](Position.md) - 持仓对象
