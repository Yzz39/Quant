# record - 记录指标

记录自定义指标,用于回测分析图表显示。

## 函数签名

```python
record(**kwargs)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| **kwargs | key-value | 指标名和值 |

## 示例

```python
def handle_data(context, data):
    # 记录价格
    price = get_price('000001.XSHE', count=1, fields='close')
    record(stock_price=price)
    
    # 记录多个指标
    record(
        ma5=ma5_value,
        ma20=ma20_value,
        position_ratio=context.portfolio.positions_value / context.portfolio.total_value
    )
```

## 注意事项

1. record的数据会在回测图表中显示
2. 可以记录任意数量指标
3. 指标名不能重复
