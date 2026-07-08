# Context - 策略上下文对象

策略运行时的上下文对象，包含账户、时间、策略等信息。

## 主要属性

### 时间相关

- **current_dt**: datetime.datetime - 当前单位时间的开始时间
- **previous_date**: datetime.date - 前一个交易日

### 账户相关

- **portfolio**: Portfolio - 账户信息（所有仓位汇总）
- **subportfolios**: list[SubPortfolio] - 各子账户信息列表

### 策略相关

- **universe**: list - 当前设置的股票池
- **run_params**: dict - 策略运行参数

## 使用示例

### 获取时间信息

```python
def handle_data(context, data):
    # 获取当前时间
    now = context.current_dt

    # 获取年月日
    year = now.year
    month = now.month
    day = now.day

    # 格式化日期
    date_str = now.strftime("%Y-%m-%d")

    # 获取前一个交易日
    prev_date = context.previous_date
```

### 获取账户信息

```python
def handle_data(context, data):
    # 获取总资产
    total_value = context.portfolio.total_value

    # 获取可用资金
    available_cash = context.portfolio.available_cash

    # 获取持仓市值
    positions_value = context.portfolio.positions_value

    # 获取累计收益
    returns = context.portfolio.returns
```

### 获取持仓信息

```python
def handle_data(context, data):
    # 遍历持仓
    for security in context.portfolio.positions:
        position = context.portfolio.positions[security]

        # 持仓数量
        total_amount = position.total_amount

        # 可卖数量
        closeable_amount = position.closeable_amount

        # 持仓市值
        value = position.value

        # 持仓成本
        avg_cost = position.avg_cost
```

### 子账户操作

```python
def handle_data(context, data):
    # 获取第一个子账户
    subportfolio = context.subportfolios[0]

    # 子账户可用资金
    cash = subportfolio.available_cash

    # 子账户持仓
    positions = subportfolio.long_positions
```

## 运行参数

context.run_params 包含以下信息：

- **start_date**: 回测/模拟开始日期
- **end_date**: 回测/模拟结束日期
- **type**: 运行方式 ('simple_backtest', 'full_backtest', 'sim_trade')
- **frequency**: 运行频率 ('day', 'minute', 'tick')

## 注意事项

1. context 对象在每次策略运行时都会更新
2. 可以向 context 添加自定义变量（会持久保存）
3. 以 '__' 开头的变量不会被持久保存

## 相关对象

- [Portfolio](Portfolio.md) - 账户信息对象
- [SubPortfolio](SubPortfolio.md) - 子账户对象
- [Position](Position.md) - 持仓对象
