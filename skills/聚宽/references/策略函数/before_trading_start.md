# before_trading_start - 开盘前运行

在每个交易日开盘前(9:00)运行。

## 函数签名

```python
def before_trading_start(context):
    pass
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| context | Context | 上下文对象 |

## 示例

```python
def initialize(context):
    # 注册开盘前函数
    run_daily(before_trading_start, time='before_open')

def before_trading_start(context):
    log.info(f"开盘前运行: {context.current_dt}")
    
    # 获取最新数据
    # 选股
    # 计算买卖列表
```

## 注意事项

1. 每天9:00运行一次
2. 此时当日行情数据尚未开始
3. 适合做盘前准备
4. 可以与handle_data或定时函数同时使用
