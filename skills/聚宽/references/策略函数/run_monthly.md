# run_monthly - 按月运行

设置每月运行的定时任务。

## 函数签名

```python
run_monthly(func, monthday=1, time='9:30', reference_security=None, force=True)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| func | function | 要运行的函数 |
| monthday | int | 每月第几个交易日 |
| time | str | 运行时间 |
| reference_security | str | 参照证券 |
| force | bool | 是否就近执行 |

## 示例

```python
def initialize(context):
    # 每月第一个交易日9:30运行
    run_monthly(monthly_rebalance, monthday=1, time='9:30')
    
    # 每月最后一个交易日运行
    run_monthly(monthly_check, monthday=-1, time='15:00')

def monthly_rebalance(context):
    log.info("月度调仓")
```

## 注意事项

1. monthday可以是负数,表示倒数
2. monthday从策略开始日计算,不是从月初
3. force=True时会找最近的交易日执行
