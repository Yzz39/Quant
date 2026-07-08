# write_file - 写入文件

将数据写入私有文件。

## 函数签名

```python
write_file(filename, content)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| filename | str | 文件名 |
| content | str | 文件内容 |

## 示例

```python
# 保存数据
data = "2024-01-01, 100, 200"
write_file("result.csv", data)

# 保存分析结果
result = "回测收益率: 20%"
write_file("analysis.txt", result)
```

## 注意事项

1. 只能写入策略私有目录
2. 不能写任意路径
3. 文件大小有限制
4. 回测和实盘文件隔离
