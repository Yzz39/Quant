# margincash_open - 融资开仓

融资买入证券。

## 函数签名

```python
margincash_open(security, amount)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| security | str | 证券代码 |
| amount | float | 买入金额 |

## 示例

```python
# 融资买入10万元
margincash_open('000001.XSHE', 100000)

# 融资买入,使用所有可用额度
cash = context.portfolio.margin_account.available_cash
margincash_open('000001.XSHE', cash)
```

## 注意事项

1. 必须先启用融资融券
2. 需要支付融资利息
3. 有融资额度限制
4. 需要维持保证金比例

## 相关函数

- [margincash_close](margincash_close.md) - 融券平仓
- [marginsec_open](marginsec_open.md) - 融券开仓
