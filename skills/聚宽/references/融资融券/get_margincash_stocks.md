# get_margincash_stocks - 获取融资标的

获取可以进行融资交易的证券列表。

## 函数签名

```python
get_margincash_stocks(date=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| date | str/datetime | 查询日期 |

## 返回值

返回 list,包含融资标的证券代码。

## 示例

```python
# 获取融资标的
margin_stocks = get_margincash_stocks()
print(len(margin_stocks))

# 获取历史融资标的
margin_stocks = get_margincash_stocks(date='2024-01-01')
```
