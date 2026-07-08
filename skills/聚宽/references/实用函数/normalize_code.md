# normalize_code - 标准化证券代码

将证券代码转换为标准格式。

## 函数签名

```python
normalize_code(code)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| code | str | 证券代码 |

## 返回值

返回标准格式的证券代码。

## 示例

```python
# 转换为标准格式
code1 = normalize_code('000001')  # '000001.XSHE'
code2 = normalize_code('600000')  # '600000.XSHG'
code3 = normalize_code('000001.XSHE')  # '000001.XSHE'
```

## 注意事项

1. 自动识别交易所
2. 已是标准格式则不变
3. 方便处理不同格式代码
