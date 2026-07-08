# set_order_cost - 设置手续费

设置交易的手续费和印花税。

## 函数签名

```python
set_order_cost(cost, type='stock')
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| cost | OrderCost | 费用设置对象 |
| type | str | 证券类型 |

## OrderCost参数

```python
OrderCost(
    open_tax=0,           # 买入时印花税
    close_tax=0.001,      # 卖出时印花税
    open_commission=0.0003,   # 买入佣金(万分之一)
    close_commission=0.0003,  # 卖出佣金
    min_commission=5       # 最低佣金(元)
)
```

## 示例

```python
def initialize(context):
    # 设置股票手续费
    set_order_cost(
        OrderCost(
            open_tax=0,           # 股票买入无印花税
            close_tax=0.001,      # 卖出印花税0.1%
            open_commission=0.0003,   # 佣金万分之一
            close_commission=0.0003,
            min_commission=5       # 最低5元
        ),
        type='stock'
    )
    
    # 设置基金手续费
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0,     # 很多基金免佣金
            close_commission=0,
            min_commission=0
        ),
        type='fund'
    )
```

## 注意事项

1. 印花税:股票卖出0.1%,买入免征
2. 佣金:最低5元,注意小额交易
3. 不同证券类型费用不同
4. 手续费影响回测结果
