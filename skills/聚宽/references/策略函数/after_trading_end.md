# after_trading_end - 收盘后运行

在每个交易日收盘后运行。

## 函数签名

```python
def after_trading_end(context):
    pass
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| context | Context | 上下文对象 |

## 示例

```python
def initialize(context):
    run_daily(after_trading_end, time='after_close')

def after_trading_end(context):
    log.info("收盘后运行")
    
    # 统计当日交易
    trades = get_trades()
    for trade_id, trade in trades.items():
        log.info(f"成交: {trade.security}, {trade.amount}")
    
    # 查看持仓
    log.info(f"总资产: {context.portfolio.total_value}")
```

## 注意事项

1. 收盘后运行
2. 可以进行统计分析
3. 此时不可下单
