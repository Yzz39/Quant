# get_current_tick - 获取当前Tick数据

获取指定证券的最新Tick数据。

## 函数签名

```python
get_current_tick(securities)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| securities | str/list | 证券代码或列表 |

## 返回值

返回 dict,key为证券代码,value为Tick数据。

## 示例

```python
# 获取单只股票的tick
tick = get_current_tick('000001.XSHE')
print(tick['current'])

# 获取多只股票的tick
ticks = get_current_tick(['000001.XSHE', '000002.XSHE'])
```
