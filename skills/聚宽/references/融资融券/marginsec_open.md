# marginsec_open - 融券开仓

融券卖出证券。

## 函数签名

```python
marginsec_open(security, amount)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| amount | float | 卖出金额 |

## 示例

```python
# 融券卖出
marginsec_open('000001.XSHE', 100000)
```

## 注意事项

1. 借证券卖出
2. 需要提供保证金
3. 需要支付融券利息
4. 未来需要买回还券
