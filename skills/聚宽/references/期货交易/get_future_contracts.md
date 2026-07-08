# get_future_contracts - 获取期货合约

获取期货品种的所有合约信息。

## 函数签名

```python
get_future_contracts(underlying_symbol)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| underlying_symbol | str | 期货品种代码 |

## 常用期货品种

### 金融期货(CCFX)

- **IF**: 沪深300股指期货
- **IH**: 上证50股指期货
- **IC**: 中证500股指期货
- **IM**: 中证1000股指期货
- **T**: 10年期国债期货
- **TF**: 5年期国债期货
- **TS**: 2年期国债期货

### 商品期货

- **AU**: 黄金(XSGE)
- **AG**: 白银(XSGE)
- **CU**: 铜(XSGE)
- **AL**: 铝(XSGE)
- **RB**: 螺纹钢(XDCE)
- **I**: 铁矿石(XDCE)
- **M**: 豆粕(XDCE)
- **Y**: 豆油(XDCE)
- **A**: 豆一(XDCE)
- **P**: 棕榈油(XDCE)

## 返回值

返回 list,包含所有合约代码。

## 示例

```python
# 获取沪深300股指期货的所有合约
contracts = get_future_contracts('IF')
print(contracts)
# ['IF2401.CCFX', 'IF2402.CCFX', 'IF2403.CCFX', ...]

# 获取主力合约
dominant = get_dominant_future('IF')
print(dominant)
```

## 注意事项

1. 不同交易所的品种代码可能重复
2. 合约代码格式: 品种+月份+交易所
3. 主力合约是成交量最大的合约

## 相关函数

- [get_dominant_future](get_dominant_future.md) - 获取主力合约
