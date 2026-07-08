# get_trades - 获取成交记录

获取当日或指定日期的成交记录。

## 函数签名

```python
get_trades(date=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| date | str/datetime | 查询日期,默认为当天 |

## 返回值

返回 dict,key为成交ID,value为Trade对象。

## 示例

```python
def after_trading_end(context):
    # 获取当日所有成交
    trades = get_trades()
    
    for trade_id, trade in trades.items():
        log.info(f"证券: {trade.security}")
        log.info(f"方向: {trade.side}")
        log.info(f"价格: {trade.price}")
        log.info(f"数量: {trade.amount}")
```

## 注意事项

1. 只返回实际成交的记录
2. 挂单未成交不在返回中
3. 回测中获取历史成交需要指定日期
