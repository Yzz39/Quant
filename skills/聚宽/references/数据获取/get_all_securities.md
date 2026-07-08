# get_all_securities - 获取所有证券代码

获取聚宽平台支持的所有证券代码及其基本信息。

## 函数签名

```python
get_all_securities(types=[], date=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| types | list | 证券类型列表,如 ['stock', 'fund', 'index', 'futures'] |
| date | str/datetime | 查询日期,默认为当前日期 |

## 支持的证券类型

- **stock**: 股票
- **fund**: 基金
- **index**: 指数
- **futures**: 期货
- **etf**: ETF基金
- **lof**: LOF基金
- **fja**: 分级基金A
- **fjb**: 分级基金B

## 返回值

返回 pandas.DataFrame,索引为证券代码,包含以下列:

| 列名 | 说明 |
|------|------|
| start_date | 上市日期 |
| end_date | 退市日期 |
| type | 证券类型 |
| parent | 上级指数(对成分股) |

## 示例

### 获取所有股票

```python
# 获取所有股票代码
all_stocks = get_all_securities(['stock'])
print(len(all_stocks))  # 股票数量
```

### 获取所有指数

```python
# 获取所有指数
all_indices = get_all_securities(['index'])
print(all_indices.index.tolist())
```

### 获取所有基金

```python
# 获取所有基金(包括ETF, LOF等)
all_funds = get_all_securities(['fund', 'etf', 'lof'])
```

### 指定日期查询

```python
# 获取某个日期的所有证券
securities = get_all_securities(['stock'], date='2020-01-01')
```

### 获取特定股票信息

```python
# 获取所有股票信息
stocks = get_all_securities(['stock'])

# 查询特定股票
print(stocks.loc['000001.XSHE'])

# 获取股票名称
# 注意: 聚宽中需要通过其他方式获取股票名称
```

## 注意事项

1. 返回的数据包含已退市的股票
2. date 参数可以查询历史某个时点的证券列表
3. 不同日期的证券列表可能不同(新上市、退市等)

## 相关函数

- [get_index_stocks](get_index_stocks.md) - 获取指数成分股
- [get_industry_stocks](get_industry_stocks.md) - 获取行业成分股
