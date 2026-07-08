# handle_tick - Tick数据处理

处理Tick数据的函数。

## 函数签名

```python
def handle_tick(context, tick):
    pass
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| context | Context | 上下文对象 |
| tick | dict | Tick数据 |

## Tick对象属性

| 属性 | 类型 | 说明 |
|------|------|------|
| code | str | 证券代码 |
| time | datetime | 时间戳 |
| current | float | 最新价 |
| volume | float | 成交量 |
| money | float | 成交额 |
| a1_p~a5_p | float | 卖一到卖五价 |
| a1_v~a5_v | float | 卖一到卖五量 |
| b1_p~b5_p | float | 买一到买五价 |
| b1_v~b5_v | float | 买一到买五量 |

## 示例

```python
def handle_tick(context, tick):
    security = tick['code']
    current_price = tick['current']
    
    # 获取买卖价差
    if tick['a1_p'] and tick['b1_p']:
        spread = tick['a1_p'] - tick['b1_p']
        log.info(f"价差: {spread}")
```

## 注意事项

1. 只在tick频率策略中使用
2. 数据量大,处理要快
3. 注意性能优化
