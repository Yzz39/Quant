# send_message - 发送消息

发送消息到手机或邮箱(仅实盘/模拟)。

## 函数签名

```python
send_message(message)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| message | str | 消息内容 |

## 示例

```python
def handle_data(context, data):
    # 发送交易提醒
    if context.portfolio.positions_value > 1000000:
        send_message("持仓市值超过100万")
```

## 注意事项

1. 仅在实盘和模拟交易中可用
2. 回测中不实际发送
3. 有发送频率限制
