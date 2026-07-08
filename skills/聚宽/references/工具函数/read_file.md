# read_file - 读取文件

读取私有文件内容。

## 函数签名

```python
read_file(filename)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| filename | str | 文件名 |

## 返回值

返回文件内容字符串。

## 示例

```python
# 读取之前保存的数据
data = read_file("result.csv")

# 读取配置
config = read_file("config.txt")
```

## 注意事项

1. 只能读取策略私有目录的文件
2. 文件必须已存在
3. 与write_file配套使用
