# Portfolio - 账户对象

表示整个账户的信息,包含总资产、持仓、收益等。

## 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| total_value | float | 总资产(现金+持仓市值) |
| positions_value | float | 持仓市值 |
| total_balance | float | 总现金 |
| available_cash | float | 可用现金 |
| locked_cash | float | 冻结现金(挂单占用) |
| positions | dict | 持仓字典,key为证券代码 |
| start_date | datetime | 策略开始日期 |
| daily_pnl | float | 当日盈亏 |
| daily_returns | float | 当日收益率 |

## 示例

```python
def handle_data(context, data):
    portfolio = context.portfolio
    
    # 获取总资产
    total_value = portfolio.total_value
    
    # 获取持仓市值
    positions_value = portfolio.positions_value
    
    # 获取可用现金
    cash = portfolio.available_cash
    
    # 计算仓位比例
    position_ratio = positions_value / total_value
    
    log.info(f"总资产: {total_value}")
    log.info(f"仓位: {position_ratio*100}%")
```

## 注意事项

1. Portfolio 对象通过 context.portfolio 访问
2. total_value = available_cash + locked_cash + positions_value

## 相关对象

- [SubPortfolio](SubPortfolio.md) - 子账户对象
- [Position](Position.md) - 持仓对象
