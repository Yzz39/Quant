# get_industry_stocks - 获取行业成分股

获取某个行业的所有成分股。

## 函数签名

```python
get_industry_stocks(industry_code, date=None)
```

## 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| industry_code | str | 行业代码 |
| date | str/datetime | 查询日期,默认为当前日期 |

## 行业分类体系

聚宽支持多种行业分类:

### 申万行业分类

#### 一级行业

- **sw1 agriculture**: 农林牧渔
- **sw1 mining**: 采掘
- **sw1 food_beverage**: 食品饮料
- **sw1 textile**: 纺织服装
- **sw1 light_manufacturing**: 轻工制造
- **sw1 medicine**: 医药生物
- **sw1 public_utility**: 公用事业
- **sw1 transportation**: 交通运输
- **sw1 real_estate**: 房地产
- **sw1 commerce**: 商业贸易
- **sw1 services**: 休闲服务
- **sw1 comprehensive**: 综合
- **sw1 building_materials**: 建筑材料
- **sw1 building_decoration**: 建筑装饰
- **sw1 electrical_equipment**: 电气设备
- **sw1 household_appliances**: 家用电器
- **sw1 electronics**: 电子
- **sw1 computer**: 计算机
- **sw1 media**: 传媒
- **sw1 communications**: 通信
- **sw1 bank**: 银行
- **sw1 non_bank_financial**: 非银金融
- **sw1 automotive**: 汽车
- **sw1 machinery**: 机械设备
- **sw1 defense**: 国防军工
- **sw1 nonferrous_metals**: 有色金属
- **sw1 chemicals**: 化工
- **sw1 steel**: 钢铁

#### 二级行业

使用 **sw2** 前缀,如 `sw2白酒`

#### 三级行业

使用 **sw3** 前缀,如 `sw3白酒III`

### 聚宽行业分类

- **jn_energy**: 能源
- **jn_materials**: 材料
- **jn_consumer discretionary**: 可选消费
- **jn_consumer staples**: 必需消费
- **jn_health_care**: 医疗保健
- **jn_financials**: 金融
- **jn_information_technology**: 信息技术
- **jn_telecommunication**: 电信服务
- **jn_utilities**: 公用事业
- **jn_industrials**: 工业

## 返回值

返回 list,包含该行业的所有成分股代码。

## 示例

### 获取申万一级行业成分股

```python
# 获取医药生物行业成分股
medicine_stocks = get_industry_stocks('sw1 medicine')
print(len(medicine_stocks))
print(medicine_stocks[:10])
```

### 获取银行股

```python
# 获取银行股
bank_stocks = get_industry_stocks('sw1 bank')
```

### 获取食品饮料行业

```python
# 获取食品饮料行业
food_stocks = get_industry_stocks('sw1 food_beverage')

# 进一步获取白酒细分行业
baijiu_stocks = get_industry_stocks('sw2 白酒')
```

### 策略应用

```python
def initialize(context):
    # 获取多个行业的股票
    industries = ['sw1 medicine', 'sw1 food_beverage', 'sw1 bank']
    g.stock_pool = []
    
    for industry in industries:
        stocks = get_industry_stocks(industry)
        g.stock_pool.extend(stocks)
```

### 历史查询

```python
# 获取2020年的医药生物成分股
stocks_2020 = get_industry_stocks('sw1 medicine', date='2020-01-01')
```

## 注意事项

1. 行业成分股会定期调整
2. 使用历史日期查询可以避免未来函数
3. 不同行业分类体系的行业代码格式不同
4. 申万行业分类更常用

## 行业轮动策略示例

```python
def before_trading_start(context):
    # 获取各行业股票
    industries = ['sw1 bank', 'sw1 medicine', 'sw1 electronics']
    
    for industry in industries:
        stocks = get_industry_stocks(industry)
        # 计算行业表现
        # ...
```

## 相关函数

- [get_all_securities](get_all_securities.md) - 获取所有证券
- [get_index_stocks](get_index_stocks.md) - 获取指数成分股
