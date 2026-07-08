# initialize - 初始化函数

策略的初始化函数，在整个策略运行期间只运行一次。

## 函数签名

```python
def initialize(context):
    # 初始化代码
    pass
```

## 参数

- **context**: Context 对象，包含策略的上下文信息

## 用途

initialize 函数用于策略的初始化设置，包括：

1. 设置基准
2. 设置手续费
3. 设置股票池
4. 设置定时任务
5. 初始化全局变量
6. 设置交易选项

## 使用示例

### 基本设置

```python
def initialize(context):
    # 设置基准为沪深300
    set_benchmark('000300.XSHG')

    # 开启动态复权模式
    set_option('use_real_price', True)

    # 设置股票手续费
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5
    ), type='stock')
```

### 设置股票池

```python
def initialize(context):
    # 设置股票池
    g.stocks = ['000001.XSHE', '000002.XSHE', '600000.XSHG']

    # 或者使用函数获取股票池
    g.stocks = get_index_stocks('000300.XSHG')  # 沪深300成分股
```

### 设置定时任务

```python
def initialize(context):
    # 每天开盘前运行
    run_daily(before_trading_start, time='before_open')

    # 每天开盘运行
    run_daily(market_open, time='open')

    # 每天收盘后运行
    run_daily(after_trading_end, time='after_close')

    # 每月1号运行
    run_monthly(rebalance, monthday=1, time='open')
```

### 初始化全局变量

```python
def initialize(context):
    # 使用 g 对象存储全局变量
    g.security = '000001.XSHE'
    g.count = 0
    g.buy_threshold = 1.05
    g.sell_threshold = 0.95
```

### 期货账户设置

```python
def initialize(context):
    # 获取初始资金
    init_cash = context.portfolio.starting_cash

    # 设置期货账户
    set_subportfolios([
        SubPortfolioConfig(cash=init_cash, type='futures')
    ])
```

### 融资融券账户设置

```python
def initialize(context):
    # 获取初始资金
    init_cash = context.portfolio.starting_cash

    # 设置融资融券账户
    set_subportfolios([
        SubPortfolioConfig(cash=init_cash, type='stock_margin')
    ])
```

### 多账户设置

```python
def initialize(context):
    # 获取初始资金并平分
    init_cash = context.portfolio.starting_cash / 3

    # 设置三个子账户
    set_subportfolios([
        SubPortfolioConfig(cash=init_cash, type='stock'),        # 股票账户
        SubPortfolioConfig(cash=init_cash, type='futures'),      # 期货账户
        SubPortfolioConfig(cash=init_cash, type='stock_margin')  # 融资融券账户
    ])
```

## 注意事项

1. initialize 函数只运行一次，不要放入需要重复执行的逻辑
2. 全局变量使用 g 对象存储，方便在其他函数中访问
3. 定时任务需要在 initialize 中设置
4. 设置选项会影响整个策略的运行

## 相关函数

- [handle_data](handle_data.md) - 数据处理函数
- [before_trading_start](before_trading_start.md) - 盘前运行函数
- [after_trading_end](after_trading_end.md) - 盘后运行函数
- [run_daily](run_daily.md) - 定时运行设置
- [run_monthly](run_monthly.md) - 定月运行设置
