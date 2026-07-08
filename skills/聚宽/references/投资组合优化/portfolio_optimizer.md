# portfolio_optimizer - 投资组合优化器

用于计算在某些约束条件下的最优组合权重。

## 函数签名

```python
from jqlib.optimizer import *

portfolio_optimizer(date, securities, target, constraints,
                    bounds=[Bound(0.0, 1.0)],
                    default_port_weight_range=[0.0, 1.0],
                    ftol=1e-9,
                    return_none_if_fail=True)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| date | datetime | 优化发生的日期 |
| securities | list | 股票代码列表 |
| target | 优化目标 | 目标函数，详见下方 |
| constraints | list | 限制函数列表 |
| bounds | list | 边界函数列表 |
| default_port_weight_range | list | 默认组合权重范围 [low, high] |
| ftol | float | 优化触发结束的函数值 |
| return_none_if_fail | bool | 失败时是否返回 None |

## 优化目标函数 (target)

### 1. MinVariance - 组合风险最小化

```python
target = MinVariance(count=250)
```

最小化组合方差。

### 2. MaxProfit - 组合收益最大化

```python
target = MaxProfit(count=250)
```

最大化组合收益。

### 3. MaxSharpeRatio - 组合夏普比率最大化

```python
target = MaxSharpeRatio(rf=0.0, weight_sum_equal=1.0, count=250)
```

- rf: 年化无风险利率
- weight_sum_equal: 组合总权重的值

### 4. MinTrackingError - 追踪误差最小化

```python
target = MinTrackingError(benchmark='000300.XSHG', count=250)
```

- benchmark: 基准的 ticker

### 5. RiskParity - 风险平价

```python
target = RiskParity(count=250, risk_budget=None)
```

- risk_budget: 风险预算，pandas.Series

### 6. MaxScore - 打分最大化

```python
target = MaxScore(scores=pd.Series([0.1, 0.2, 0.3],
                                   index=['000001.XSHE', '000002.XSHE', '000005.XSHE']))
```

### 7. MinScore - 打分最小化

```python
target = MinScore(scores)
```

### 8. MaxFactorValue - 因子值最大化

```python
from jqfactor import Factor

class AR(Factor):
    name = 'AR'
    max_window = 5
    dependencies = ['AR']
    def calc(self, data):
        return data['AR'].mean()

target = MaxFactorValue(factor=AR, count=1)
```

## 限制函数 (constraints)

### WeightConstraint - 组合总权重限制

```python
constraint = WeightConstraint(low=0.5, high=0.9)
```

### WeightEqualConstraint - 组合总权重和限制

```python
constraint = WeightEqualConstraint(limit=1.0)
```

### AnnualStdConstraint - 年化收益率标准差限制

```python
constraint = AnnualStdConstraint(limit=0.15, count=250)
```

### AnnualProfitConstraint - 年化收益率预期限制

```python
constraint = AnnualProfitConstraint(limit=0.1, count=250)
```

### IndustryConstraint - 行业权重限制

```python
constraint = IndustryConstraint(['HY001'], low=0.0, high=0.2)
```

### MarketConstraint - 市场权重限制

```python
constraint = MarketConstraint('stock', low=0.0, high=0.9)
constraint = MarketConstraint('etf', low=0.0, high=0.1)
```

## 边界函数 (bounds)

### Bound - 每只标的的权重限制

```python
bound = Bound(low=0.0, high=0.1)
```

### IndustryBound - 行业内股票权重限制

```python
bound = IndustryBound(['HY001', 'HY007'], low=0.0, high=0.05)
```

## 完整示例

```python
from jqdata import *
from jqfactor import Factor
from jqlib.optimizer import *

def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(OrderCost(close_tax=0.001, open_commission=0.0003,
                            close_commission=0.0003, min_commission=5), type='stock')
    run_monthly(rebalance, monthday=1, time='open')

def rebalance(context):
    # 股票池
    buy_list = get_index_stocks('000016.XSHG')[-15:]  # 上证50部分成分股

    # 风险平价优化
    optimized_weight = portfolio_optimizer(
        date=context.previous_date,
        securities=buy_list,
        target=RiskParity(count=250),
        constraints=[
            MarketConstraint('stock', low=0.0, high=0.9)
        ],
        bounds=[Bound(0, 0.1)],
        default_port_weight_range=[0., 1.0]
    )

    # 按优化结果调仓
    if optimized_weight is not None:
        total_value = context.portfolio.total_value
        for stock in buy_list:
            if stock in optimized_weight.index:
                value = total_value * optimized_weight[stock]
                order_target_value(stock, value)
```

## 注意事项

1. 优化器的计算需要历史数据，count 参数应足够大
2. 注意未来函数风险，date 参数不应使用未来日期
3. 优化可能失败，需要检查返回值
4. 约束条件设置要合理，避免无解

## 相关文档

- [优化目标函数详解](优化目标函数.md)
- [限制函数详解](限制函数.md)
- [边界函数详解](边界函数.md)
