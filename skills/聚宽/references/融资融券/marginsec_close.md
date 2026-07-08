# marginsec_close - 融券平仓

买入证券归还融券。

## 函数签名

```python
marginsec_close(security, amount)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| amount | float | 买入金额 |

## 示例

```python
# 买券还券
marginsec_close('000001.XSHE', 100000)
```

## 注意事项

1. 买入证券归还
2. 归还后融券负债减少
