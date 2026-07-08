# handle_data - 数据处理函数

策略的核心交易函数，每个 bar（天/分钟）调用一次。

## 函数签名

```python
def handle_data(context, data):
    # 交易逻辑
    pass
```

## 参数

- **context**: Context 对象，包含策略上下文信息
- **data**: dict，键是标的代码，值是 SecurityUnitData 对象

## 调用频率

- **天级回测**: 每个交易日调用一次
- **分钟级回测**: 每分钟调用一次
- **Tick 级回测**: 不调用（需使用 handle_tick）

## 使用示例

### 基本策略

```python
def handle_data(context, data):
    # 获取要操作的股票
    security = g.security

    # 获取历史数据
    hist = attribute_history(security, 5, '1d', ['close'])

    # 计算均线
    MA5 = hist['close'].mean()

    # 获取当前价格
    current_price = data[security].close

    # 交易逻辑
    if current_price > MA5 * 1.05:
        # 买入
        order_value(security, context.portfolio.available_cash)
    elif current_price < MA5 * 0.95:
        # 卖出
        order_target(security, 0)
```

### 多股票策略

```python
def handle_data(context, data):
    # 遍历股票池
    for security in g.stocks:
        # 获取当前价格
        price = data[security].close

        # 获取历史均价
        vwap = data[security].vwap(3)

        # 交易逻辑
        if price > vwap * 1.005:
            order(security, 100)
        elif price < vwap * 0.995:
            order(security, -100)
```

### 使用 record 记录数据

```python
def handle_data(context, data):
    security = g.security
    price = data[security].close

    # 记录数据用于绘图
    record(price=price)
    record(cash=context.portfolio.available_cash)
```

### 分时交易

```python
def handle_data(context, data):
    # 只在特定时间交易
    hour = context.current_dt.hour
    minute = context.current_dt.minute

    # 只在 14:00 之后交易
    if hour < 14:
        return

    # 交易逻辑
    # ...
```

## 注意事项

1. **频率控制**: handle_data 调用频繁，避免重复计算
2. **数据缓存**: 将不变的计算放在 before_trading_start 中
3. **交易限制**: 注意 A 股 T+1 交易规则
4. **成本考虑**: 频繁交易会产生高额手续费
5. **避免未来函数**: 不能使用当前 bar 之后的数据

## 与其他函数的关系

- **initialize**: 只运行一次，用于初始化
- **before_trading_start**: 每天开盘前运行一次
- **handle_data**: 每个 bar 运行一次
- **after_trading_end**: 每天收盘后运行一次

## 分钟级回测注意事项

1. 设置 frequency='minute'
2. 注意交易时间（9:30-11:30, 13:00-15:00）
3. 考虑集合竞价时间（9:15-9:25）
4. 分钟数据量更大，注意运行效率

## 相关函数

- [initialize](initialize.md) - 初始化函数
- [before_trading_start](before_trading_start.md) - 盘前函数
- [after_trading_end](after_trading_end.md) - 盘后函数
- [handle_tick](../Tick数据/handle_tick.md) - Tick 策略函数
