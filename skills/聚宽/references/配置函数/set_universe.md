# set_universe - 设置股票池

设置策略的股票池。

## 函数签名

```python
set_universe(stocks)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| stocks | list | 股票代码列表 |

## 示例

```python
def initialize(context):
    # 设置股票池
    stocks = ['000001.XSHE', '000002.XSHE', '600000.XSHG']
    set_universe(stocks)
```

## 注意事项

1. 设置股票池后,仅池内股票可交易
2. 可以动态更新股票池
3. 推荐使用g对象管理股票池

## 替代方案

```python
# 更灵活的方式
def initialize(context):
    g.stock_pool = ['000001.XSHE', '000002.XSHE']
```
