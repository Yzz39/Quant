# get_index_stocks - 获取指数成分股

获取指数在某个时间点的成分股。

## 函数签名

```python
get_index_stocks(index_symbol, date=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| index_symbol | str | 指数代码 |
| date | str/datetime | 查询日期,默认为当前日期 |

## 常用指数代码

### 市场指数

- **000001.XSHG**: 上证综指
- **399001.XSHE**: 深证成指
- **000300.XSHG**: 沪深300
- **000905.XSHG**: 中证500
- **000852.XSHG**: 中证1000

### 行业指数

- **000016.XSHG**: 上证50
- **399006.XSHE**: 创业板指
- **399005.XSHE**: 中小板指

### 策略指数

- **399372.XSHE**: 国证2000
- **399317.XSHE**: 国证1000

## 返回值

返回 list,包含成分股代码。

## 示例

### 获取沪深300成分股

```python
# 获取沪深300当前的成分股
stocks = get_index_stocks('000300.XSHG')
print(len(stocks))  # 成分股数量
print(stocks[:10])  # 前10只股票
```

### 获取历史成分股

```python
# 获取2020年1月1日的沪深300成分股
stocks = get_index_stocks('000300.XSHG', date='2020-01-01')
```

### 策略应用

```python
def initialize(context):
    # 获取沪深300成分股作为股票池
    g.stock_pool = get_index_stocks('000300.XSHG')
```

### 多个指数组合

```python
# 组合多个指数的成分股
def initialize(context):
    # 沪深300 + 中证500
    stocks_300 = get_index_stocks('000300.XSHG')
    stocks_500 = get_index_stocks('000905.XSHG')
    
    # 去重合并
    g.stock_pool = list(set(stocks_300 + stocks_500))
```

## 注意事项

1. 成分股会定期调整,不同日期的成分股可能不同
2. 历史成分股查询可以避免未来函数
3. 返回的是代码列表,不是DataFrame
4. 成分股数量可能随时间变化

## 常见用途

1. **构建股票池**: 将指数成分股作为股票池
2. **风格投资**: 投资特定风格指数(如大盘、小盘)
3. **定期调仓**: 跟踪指数成分股变化

## 相关函数

- [get_all_securities](get_all_securities.md) - 获取所有证券
- [get_industry_stocks](get_industry_stocks.md) - 获取行业成分股
