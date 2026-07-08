# history - 获取历史数据

获取多个证券的历史数据,返回 pandas.Panel 或 pandas.DataFrame 格式。

## 函数签名

```python
history(count, unit, field, security_list, df=True, skip_paused=True, fq='pre')
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| count | int | 数量,获取过去 count 个单位时间的数据 |
| unit | str | 单位时间,支持 '1d'/'1w'/'1m' 等 |
| field | str/list | 字段名,如 'open'/'close'/'high'/'low'/'volume'/'money' 等 |
| security_list | list | 证券代码列表 |
| df | bool | 是否返回 DataFrame,默认 True |
| skip_paused | bool | 是否跳过停牌日期,默认 True |
| fq | str | 复权方式,'pre' 前复权,'none' 不复权 |

## 返回值

返回 pandas.DataFrame 或 pandas.Panel 对象。

## 示例

### 获取多只股票的历史收盘价

```python
# 获取多只股票过去10天的收盘价
df = history(10, '1d', 'close', ['000001.XSHE', '000002.XSHE', '600000.XSHG'])
# 返回 DataFrame,索引为日期,列为证券代码
```

### 获取多字段数据

```python
# 获取多只股票的开高低收数据
df = history(5, '1d', ['open', 'close', 'high', 'low'],
             ['000001.XSHE', '000002.XSHE'])
```

### 与 attribute_history 的区别

**history**: 适合获取多个证券的数据,返回格式便于多证券对比
**attribute_history**: 适合获取单个证券的多个字段,返回格式便于技术分析

## 注意事项

1. history 主要用于获取多个证券的数据
2. 如果只需要单个证券的数据,建议使用 attribute_history
3. 返回的数据格式为 MultiIndex DataFrame

## 相关函数

- [get_price](get_price.md) - 获取行情数据
- [attribute_history](attribute_history.md) - 获取历史属性数据
