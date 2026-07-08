# log - 日志输出

输出日志信息。

## 函数签名

```python
log.info(message)
log.warn(message)
log.error(message)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| message | str | 日志内容 |

## 示例

```python
# 输出普通日志
log.info("策略开始运行")

# 输出警告
log.warn("持仓比例过高")

# 输出错误
log.error("下单失败")
```

## 日志级别

- **log.info**: 信息级别
- **log.warn**: 警告级别
- **log.error**: 错误级别

## 注意事项

1. 日志在回测结果中查看
2. 过多日志影响性能
3. 生产环境注意日志量
