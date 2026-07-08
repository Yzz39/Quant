# get_dominant_future - 获取主力合约

获取期货品种对应的主力合约代码。

## 函数签名

```python
get_dominant_future(underlying_symbol, date=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| underlying_symbol | str | 期货品种代码，如 'IF'、'RB' 等 |
| date | str/datetime | 查询日期，默认为策略当前日期 |

## 返回值

返回主力合约对应的期货合约代码（str）。

## 主力合约说明

- **合约代码格式**：品种代码 + 9999 + 交易所后缀
  - 例如：IF9999.CCFX（沪深300主力合约）
  - 例如：RB9999.XSGE（螺纹钢主力合约）

- **主力合约定义**：
  - 如果某合约持仓量连续2天为同一品种中最大的
  - 金融期货限定主力只从最近的两个合约中选取
  - 且该合约相对于当前主力合约为远期合约
  - 则自动变成主力合约

- **注意事项**：
  - 不可直接对主力合约进行下单
  - 需要获取主力合约对应的具体合约进行交易
  - 不会在日内进行主力合约切换

## 示例

### 获取主力合约

```python
def initialize(context):
    # 获取沪深300期货的主力合约
    dominant = get_dominant_future('IF')
    # 返回如 'IF2401.CCFX'

    # 获取螺纹钢的主力合约
    rb_dominant = get_dominant_future('RB')
    # 返回如 'RB2405.XSGE'
```

### 交易主力合约

```python
def handle_data(context, data):
    # 获取当前主力合约
    dominant_contract = get_dominant_future('IF')

    # 获取当前价格
    current_price = get_price(dominant_contract, count=1)['close'].iloc[-1]

    # 对主力合约进行交易
    if current_price > 3500:
        order(dominant_contract, 1, side='long')
```

### 历史主力合约查询

```python
def initialize(context):
    # 查询特定日期的主力合约
    if_date = '2024-01-15'
    dominant = get_dominant_future('IF', date=if_date)
    # 返回该日期的主力合约代码
```

## 主要期货交易所品种

### 中金所 (CCFX)

| 品种 | 说明 |
|------|------|
| IF | 沪深300指数期货 |
| IH | 上证50指数期货 |
| IC | 中证500指数期货 |
| IM | 中证1000指数期货 |
| TS | 2年期国债期货 |
| TF | 5年期国债期货 |
| T | 10年期国债期货 |
| TL | 30年期国债期货 |

### 上期所 (XSGE)

| 品种 | 说明 |
|------|------|
| CU | 铜 |
| AL | 铝 |
| ZN | 锌 |
| PB | 铅 |
| NI | 镍 |
| SN | 锡 |
| AU | 黄金 |
| AG | 白银 |
| RB | 螺纹钢 |
| HC | 热卷 |
| BU | 沥青 |
| RU | 橡胶 |
| SP | 纸浆 |
| FU | 燃料油 |

### 大商所 (XDCE)

| 品种 | 说明 |
|------|------|
| A | 豆一 |
| M | 豆粕 |
| Y | 豆油 |
| P | 棕榈油 |
| C | 玉米 |
| CS | 玉米淀粉 |
| L | 聚乙烯 |
| V | 聚氯乙烯 |
| PP | 聚丙烯 |
| J | 焦炭 |
| JM | 焦煤 |
| I | 铁矿石 |
| FB | 纤维板 |
| BB | 胶合板 |

### 郑商所 (XZCE)

| 品种 | 说明 |
|------|------|
| SR | 白糖 |
| CF | 棉花 |
| RM | 菜粕 |
| MA | 甲醇 |
| TA | PTA |
| OI | 菜油 |
| FG | 玻璃 |
| RS | 菜籽 |
| RI | 早籼稻 |
| WH | 强麦 |
| PM | 普麦 |
| JR | 粳稻 |

## 相关函数

- [get_future_contracts](get_future_contracts.md) - 获取可交易合约列表
- [order](../交易下单/order.md) - 期货下单
