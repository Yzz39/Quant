# get_current_data - 获取当前数据

获取证券当前的快照数据,包括是否停牌、涨跌停价等实时信息。

## 函数签名

```python
get_current_data()
```

## 参数

无参数

## 返回值

返回一个 dict,key 为证券代码,value 为 CurrentData 对象。

## CurrentData 对象属性

| 属性 | 类型 | 说明 |
|------|------|------|
| code | str | 证券代码 |
| last_price | float | 最新价 |
| day_open | float | 当日开盘价 |
| high_limit | float | 涨停价 |
| low_limit | float | 跌停价 |
| paused | bool | 是否停牌 |
| is_st | bool | 是否ST股票 |
| stopped | bool | 是否停止交易 |

## 示例

### 获取单个证券的当前数据

```python
def handle_data(context, data):
    security = '000001.XSHE'
    current_data = get_current_data()

    # 检查是否停牌
    if current_data[security].paused:
        log.info(f"{security} 已停牌,跳过交易")
        return

    # 获取最新价
    last_price = current_data[security].last_price

    # 获取涨跌停价
    high_limit = current_data[security].high_limit
    low_limit = current_data[security].low_limit

    # 检查是否ST股票
    if current_data[security].is_st:
        log.info(f"{security} 是ST股票,谨慎交易")
```

### 遍历所有证券的当前数据

```python
def before_trading_start(context):
    current_data = get_current_data()

    for security in g.stock_pool:
        # 检查停牌
        if current_data[security].paused:
            log.info(f"{security} 停牌,从股票池中移除")
            g.stock_pool.remove(security)
            continue

        # 检查是否ST
        if current_data[security].is_st:
            log.info(f"{security} 是ST股票,移除")
            g.stock_pool.remove(security)
```

## 注意事项

1. get_current_data 返回的是当前时刻的快照数据
2. 在回测中,返回的是回测当前时间点的数据
3. paused=True 表示停牌,此时无法交易
4. is_st=True 表示是ST股票,有涨跌停限制

## 常见用途

1. **检查停牌**: 避免对停牌股票下单
2. **检查ST状态**: ST股票有5%涨跌停限制
3. **获取涨跌停价**: 判断价格是否接近涨跌停
4. **获取最新价**: 用于实时决策
