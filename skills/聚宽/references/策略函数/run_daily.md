# run_daily - 按日运行

设置每天运行的定时任务。

## 函数签名

```python
run_daily(func, time='9:30', reference_security=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| func | function | 要运行的函数 |
| time | str | 运行时间 |
| reference_security | str | 参照证券 |

## time参数

- **'9:30'**: 具体时间(24小时制)
- **'open'**: 开盘时间
- **'every_bar'**: 每个bar(按天时为开盘,按分钟时为每分钟)
- **'before_open'**: 开盘前
- **'after_close'**: 收盘后

## 示例

```python
def initialize(context):
    # 每天开盘运行
    run_daily(market_open, time='open')
    
    # 每天10:00运行
    run_daily(check_position, time='10:00')
    
    # 每个bar运行
    run_daily(trade, time='every_bar')

def market_open(context):
    log.info("开盘运行")

def check_position(context):
    log.info("10:00运行")
```

## 注意事项

1. func函数只能有一个context参数
2. 不要与handle_data同时使用
3. 可以设置多个run_daily
4. time='every_bar'仅在run_daily中可用
