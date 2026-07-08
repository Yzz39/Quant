# set_benchmark - 设置基准

设置策略的基准标的，用于衡量策略表现。

## 函数签名

```python
set_benchmark(security)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 标的代码 |

## 支持的基准类型

### 指数

```python
# 沪深300
set_benchmark('000300.XSHG')

# 上证50
set_benchmark('000016.XSHG')

# 中证500
set_benchmark('000905.XSHG')

# 中证1000
set_benchmark('000852.XSHG')

# 创业板指
set_benchmark('399006.XSHE')
```

### ETF

```python
# 沪深300 ETF
set_benchmark('510300.XSHG')

# 上证50 ETF
set_benchmark('510050.XSHG')

# 中证500 ETF
set_benchmark('510500.XSHG')
```

### 个股

```python
# 以某个股票为基准
set_benchmark('600036.XSHG')
```

### 组合基准

```python
# 自定义组合基准
# 需要通过指数代码实现
```

## 使用示例

### 基本设置

```python
def initialize(context):
    # 设置沪深300为基准
    set_benchmark('000300.XSHG')
```

### 根据策略类型选择基准

```python
def initialize(context):
    # 获取股票池
    g.stocks = get_index_stocks('000016.XSHG')  # 上证50成分股

    # 设置相应基准
    if '000016.XSHG' in g.stocks:
        set_benchmark('000016.XSHG')  # 上证50
    elif '000300.XSHG' in g.stocks:
        set_benchmark('000300.XSHG')  # 沪深300
    elif '000905.XSHG' in g.stocks:
        set_benchmark('000905.XSHG')  # 中证500
```

### 动态基准（不推荐）

```python
# 可以在不同时期使用不同基准
# 但一般不建议这样做
def initialize(context):
    # 设置初始基准
    g.benchmark = '000300.XSHG'
    set_benchmark(g.benchmark)

def before_trading_start(context):
    # 根据条件切换基准（不推荐）
    if context.current_dt.month == 1:
        if g.benchmark != '000016.XSHG':
            g.benchmark = '000016.XSHG'
            # 注意：set_benchmark 不能在运行时修改
```

## 基准选择建议

### 股票策略

| 策略类型 | 推荐基准 | 原因 |
|----------|----------|------|
| 大盘股策略 | 沪深300 (000300.XSHG) | 代表大盘 |
| 蓝筹股策略 | 上证50 (000016.XSHG) | 代表蓝筹 |
| 中小盘策略 | 中证500 (000905.XSHG) | 代表中盘 |
| 小盘股策略 | 中证1000 (000852.XSHG) | 代表小盘 |
| 创业板策略 | 创业板指 (399006.XSHE) | 代表创业板 |

### 行业策略

选择对应的行业指数作为基准。

### 量化策略

通常选择沪深300作为基准。

## 注意事项

1. **必须在 initialize 中设置**: 不能在运行时修改基准
2. **选择合适的基准**: 基准应反映策略的投资范围
3. **基准必须可交易**: 基准标的需要在回测期间有数据
4. **避免过于拟合**: 基准应客观公正，不要频繁更换

## 基准评估指标

基准用于计算以下指标：

- **超额收益**: 策略收益 - 基准收益
- **Alpha**: 超过基准的收益
- **Beta**: 相对于基准的波动
- **信息比率**: 超额收益/跟踪误差
- **相对最大回撤**: 相对于基准的最大回撤

## 相关函数

- [set_option](set_option.md) - 设置其他选项
- [set_order_cost](set_order_cost.md) - 设置手续费
