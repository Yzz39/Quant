# subscribe - 订阅Tick数据

订阅指定证券的Tick数据。

## 函数签名

```python
subscribe(securities)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| securities | str/list | 证券代码或列表 |

## 示例

```python
def initialize(context):
    # 订阅单只股票
    subscribe('000001.XSHE')
    
    # 订阅多只股票
    subscribe(['000001.XSHE', '000002.XSHE'])
```

## 注意事项

1. 只在tick频率策略中有效
2. 订阅后才会接收tick数据
3. 订阅数量有限制
