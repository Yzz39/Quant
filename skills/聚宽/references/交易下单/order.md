# order - 按数量下单

买卖标的，按指定的数量进行下单。

## 函数签名

```python
order(security, amount, style=None, side='long', pindex=0, close_today=False)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 标的代码 |
| amount | int | 交易数量，正数表示买入，负数表示卖出 |
| style | OrderStyle | 下单方式，默认市价单 |
| side | str | 'long'/'short'，多单或空单 |
| pindex | int | 子账户索引，默认为0 |
| close_today | bool | 是否平今仓（期货专用） |

## 返回值

返回 Order 对象或者 None，创建委托成功返回 Order 对象，失败返回 None。

## 示例

### 基本买入

```python
# 买入 100 股平安银行
order('000001.XSHE', 100)
```

### 基本卖出

```python
# 卖出 100 股
order('000001.XSHE', -100)
```

### 限价单

```python
# 使用限价单买入
from jqlib.ordre_style import LimitOrderStyle
order('000001.XSHE', 100, LimitOrderStyle(10.50))
```

### 期货多单

```python
# 开一手沪深300指数期货多单
order('IF2401.CCFX', 1, side='long', pindex=0)
```

### 期货空单

```python
# 开一手沪深300指数期货空单
order('IF2401.CCFX', 1, side='short', pindex=0)
```

### 平今仓

```python
# 平今仓
order('IF2401.CCFX', -1, side='long', close_today=True)
```

## 注意事项

1. 股票买入数量必须是100的整数倍
2. 卖出时会检查持仓是否足够
3. 期货交易需要先设置子账户类型为 'futures'
4. 可能因资金不足、持仓不足等原因导致下单失败

## 相关函数

- [order_target](order_target.md) - 目标数量下单
- [order_value](order_value.md) - 按金额下单
- [order_target_value](order_target_value.md) - 目标金额下单
