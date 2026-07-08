---
name: joinquant
description: 聚宽量化交易平台接口，提供股票、期货等金融产品的行情数据获取、交易下单、回测模拟等功能。支持数据获取(get_price、history、attribute_history等)、交易操作(order系列函数)、账户管理、期货交易、融资融券、投资组合优化、Tick级数据等。使用场景：量化策略开发、回测、模拟交易、实盘交易、金融数据分析。
---

# joinquant

## 概述

聚宽是一个专业的量化交易平台，提供完整的量化交易工具链。该平台支持股票、期货、基金等多种金融产品的数据获取、策略回测、模拟交易和实盘交易。

主要功能模块：
- **数据获取**：获取股票、期货、基金的行情数据和财务数据
- **交易下单**：提供多种交易函数实现买入卖出操作
- **账户管理**：Context、Portfolio、Position 等账户对象管理
- **期货交易**：期货合约、主力合约、保证金等期货专用功能
- **融资融券**：融资买入、融券卖出等两融业务
- **投资组合优化**：多种优化模型构建最优投资组合
- **Tick 数据**：Tick 级行情订阅和策略运行
- **工具函数**：订单查询、成交记录、消息发送等辅助功能

## 环境配置

使用聚宽接口需要先导入相关模块：

```python
# 策略或研究中导入
from jqdata import *
from jqlib.optimizer import *
from jqfactor import Factor
```

## Scripts

无

## References

以下是聚宽平台的详细接口文档，按功能模块组织：

### 快速入门
- [安装与配置](references/快速入门/安装与配置.md)
- [基本概念](references/快速入门/基本概念.md)
- [第一个策略](references/快速入门/第一个策略.md)

### 数据获取

#### 行情数据
- [get_price - 获取历史行情数据](references/数据获取/get_price.md)
- [history - 获取历史数据](references/数据获取/history.md)
- [attribute_history - 获取历史属性数据](references/数据获取/attribute_history.md)
- [get_current_data - 获取当前数据](references/数据获取/get_current_data.md)
- [get_bars - 获取K线数据](references/数据获取/get_bars.md)
- [get_extras - 获取额外数据](references/数据获取/get_extras.md)

#### 财务数据
- [get_fundamentals - 查询财务数据](references/数据获取/get_fundamentals.md)
- [get_fundamentals_continuously - 查询多日财务数据](references/数据获取/get_fundamentals_continuously.md)
- [get_history_fundamentals - 获取历史财务数据](references/数据获取/get_history_fundamentals.md)
- [get_valuation - 获取市值数据](references/数据获取/get_valuation.md)
- [财务数据表说明 - 字段详细说明](references/数据获取/财务数据表说明.md)

#### 标的数据
- [get_all_securities - 获取所有标的](references/数据获取/get_all_securities.md)
- [get_index_stocks - 获取指数成分股](references/数据获取/get_index_stocks.md)
- [get_industry_stocks - 获取行业股票](references/数据获取/get_industry_stocks.md)
- [get_billboard_list - 获取龙虎榜数据](references/数据获取/get_billboard_list.md)

### 交易下单
- [order - 按数量下单](references/交易下单/order.md)
- [order_target - 目标数量下单](references/交易下单/order_target.md)
- [order_value - 按金额下单](references/交易下单/order_value.md)
- [order_target_value - 目标金额下单](references/交易下单/order_target_value.md)
- [batch_submit_orders - 篮子下单](references/交易下单/batch_submit_orders.md)
- [batch_cancel_orders - 篮子撤单](references/交易下单/batch_cancel_orders.md)
- [get_open_orders - 查询未成交订单](references/交易下单/get_open_orders.md)
- [cancel_order - 撤单](references/交易下单/cancel_order.md)

### 账户对象
- [Context - 策略上下文对象](references/账户对象/Context.md)
- [Portfolio - 账户信息对象](references/账户对象/Portfolio.md)
- [SubPortfolio - 子账户对象](references/账户对象/SubPortfolio.md)
- [Position - 持仓对象](references/账户对象/Position.md)
- [Order - 订单对象](references/账户对象/Order.md)
- [Trade - 成交对象](references/账户对象/Trade.md)

### 期货交易
- [get_dominant_future - 获取主力合约](references/期货交易/get_dominant_future.md)
- [get_future_contracts - 获取可交易合约](references/期货交易/get_future_contracts.md)
- [期货下单函数](references/期货交易/期货下单函数.md)
- [期货保证金设置](references/期货交易/期货保证金设置.md)

### 融资融券
- [融资融券初始化](references/融资融券/融资融券初始化.md)
- [margincash_open - 融资买入](references/融资融券/margincash_open.md)
- [margincash_close - 卖券还款](references/融资融券/margincash_close.md)
- [marginsec_open - 融券卖出](references/融资融券/marginsec_open.md)
- [marginsec_close - 买券还券](references/融资融券/marginsec_close.md)
- [get_margincash_stocks - 获取融资标的](references/融资融券/get_margincash_stocks.md)
- [get_marginsec_stocks - 获取融券标的](references/融资融券/get_marginsec_stocks.md)
- [get_mtss - 获取融资融券数据](references/融资融券/get_mtss.md)

### 投资组合优化
- [portfolio_optimizer - 组合优化器](references/投资组合优化/portfolio_optimizer.md)
- [优化目标函数](references/投资组合优化/优化目标函数.md)
- [限制函数](references/投资组合优化/限制函数.md)
- [边界函数](references/投资组合优化/边界函数.md)

### Tick 数据
- [handle_tick - Tick策略函数](references/Tick数据/handle_tick.md)
- [subscribe - 订阅Tick事件](references/Tick数据/subscribe.md)
- [unsubscribe - 取消订阅](references/Tick数据/unsubscribe.md)
- [get_current_tick - 获取当前Tick](references/Tick数据/get_current_tick.md)

### 工具函数
- [get_orders - 查询订单](references/工具函数/get_orders.md)
- [get_trades - 获取成交记录](references/工具函数/get_trades.md)
- [send_message - 发送消息](references/工具函数/send_message.md)
- [record - 记录数据](references/工具函数/record.md)
- [log - 日志函数](references/工具函数/log.md)
- [write_file - 写文件](references/工具函数/write_file.md)
- [read_file - 读文件](references/工具函数/read_file.md)

### 策略函数
- [initialize - 初始化函数](references/策略函数/initialize.md)
- [handle_data - 数据处理函数](references/策略函数/handle_data.md)
- [before_trading_start - 盘前运行](references/策略函数/before_trading_start.md)
- [after_trading_end - 盘后运行](references/策略函数/after_trading_end.md)
- [run_daily - 定时运行](references/策略函数/run_daily.md)
- [run_monthly - 定月运行](references/策略函数/run_monthly.md)

### 配置函数
- [set_benchmark - 设置基准](references/配置函数/set_benchmark.md)
- [set_option - 设置选项](references/配置函数/set_option.md)
- [set_order_cost - 设置手续费](references/配置函数/set_order_cost.md)
- [set_universe - 设置股票池](references/配置函数/set_universe.md)

### 实用函数
- [normalize_code - 代码格式转换](references/实用函数/normalize_code.md)
- [get_trade_days - 获取交易日](references/实用函数/get_trade_days.md)

## 数据查询

使用 Grep 在聚宽文档中搜索特定 API：

```bash
# 搜索特定函数
grep -r "def get_price" references/

# 搜索特定概念
grep -r "期货" references/
```

## 相关链接

- 聚宽官网：https://www.joinquant.com/
- API 文档：https://www.joinquant.com/help/api/help
- 策略示例：https://www.joinquant.com/help/api/help#Stock
- 社区讨论：https://www.joinquant.com/community
