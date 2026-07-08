# margincash_close - 融资平仓

卖出融资买入的证券,归还资金。

## 函数签名

```python
margincash_close(security, amount)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| amount | float | 卖出金额 |

## 示例

```python
# 平掉融资仓位
margincash_close('000001.XSHE', 100000)

# 全部平仓
position = context.portfolio.margin_account.positions['000001.XSHE']
margincash_close('000001.XSHE', position.value)
```

## 注意事项

1. 只能卖出融资买入的证券
2. 卖出后自动归还融资款
3. 按先入先出原则
