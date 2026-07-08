# set_option - 设置选项

设置策略的各种选项。

## 函数签名

```python
set_option(key, value)
```

## 常用选项

### use_real_price - 动态复权

```python
set_option('use_real_price', True)
```

- True: 使用动态复权价格
- False: 使用前复权价格

### order_volume_ratio - 成交量限制

```python
set_option('order_volume_ratio', 0.25)
```

限制单个订单成交量不超过当日总成交量的比例。

### 其他选项

```python
# 持仓限制
set_option('hold_max', 100)  # 最大持仓数量

# 其他配置...
```

## 示例

```python
def initialize(context):
    # 开启动态复权
    set_option('use_real_price', True)
    
    # 设置成交量限制
    set_option('order_volume_ratio', 0.25)
```

## 注意事项

1. use_real_price建议设为True
2. order_volume_ratio影响回测真实性
3. 部分选项仅对特定情况有效
