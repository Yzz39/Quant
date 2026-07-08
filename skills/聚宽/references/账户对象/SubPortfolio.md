# SubPortfolio - 子账户对象

表示子账户信息,用于融资融券等场景。

## 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| total_value | float | 子账户总资产 |
| positions | dict | 子账户持仓 |
| total_balance | float | 子账户总现金 |
| available_cash | float | 子账户可用现金 |

## 示例

```python
# 融资融券账户
margin_portfolio = context.portfolio.margin_account
```

## 注意事项

1. 融资融券时会有普通账户和信用账户两个子账户
2. 普通策略一般不涉及SubPortfolio

## 相关对象

- [Portfolio](Portfolio.md) - 账户对象
