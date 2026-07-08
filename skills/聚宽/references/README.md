# 聚宽(JoinQuant) API 参考文档

本目录包含聚宽量化平台的完整API参考文档。

## 文档结构

### 快速入门
- [安装与配置](快速入门/安装与配置.md) - 平台介绍、环境配置
- [基本概念](快速入门/基本概念.md) - 标的代码、策略生命周期、核心对象
- [第一个策略](快速入门/第一个策略.md) - 双均线策略示例

### 数据获取
- [get_price](数据获取/get_price.md) - 获取历史行情数据
- [history](数据获取/history.md) - 获取多个证券历史数据
- [attribute_history](数据获取/attribute_history.md) - 获取历史属性数据
- [get_current_data](数据获取/get_current_data.md) - 获取当前快照数据
- [get_bars](数据获取/get_bars.md) - 获取K线数据
- [get_extras](数据获取/get_extras.md) - 获取额外数据(涨跌幅等)
- [get_fundamentals](数据获取/get_fundamentals.md) - 查询财务数据
- [get_fundamentals_continuously](数据获取/get_fundamentals_continuously.md) - 查询多日财务数据
- [get_history_fundamentals](数据获取/get_history_fundamentals.md) - 获取历史财务数据
- [get_valuation](数据获取/get_valuation.md) - 获取市值数据
- [财务数据表说明](数据获取/财务数据表说明.md) - 财务数据字段详解
- [get_all_securities](数据获取/get_all_securities.md) - 获取所有证券代码
- [get_index_stocks](数据获取/get_index_stocks.md) - 获取指数成分股
- [get_industry_stocks](数据获取/get_industry_stocks.md) - 获取行业成分股
- [get_billboard_list](数据获取/get_billboard_list.md) - 获取龙虎榜数据

### 交易下单
- [order](交易下单/order.md) - 按数量下单
- [order_target](交易下单/order_target.md) - 目标数量下单
- [order_value](交易下单/order_value.md) - 按金额下单
- [order_target_value](交易下单/order_target_value.md) - 目标金额下单
- [batch_submit_orders](交易下单/batch_submit_orders.md) - 批量下单
- [batch_cancel_orders](交易下单/batch_cancel_orders.md) - 批量撤单
- [get_open_orders](交易下单/get_open_orders.md) - 获取未成交订单
- [cancel_order](交易下单/cancel_order.md) - 撤销订单

### 账户对象
- [Context](账户对象/Context.md) - 上下文对象
- [Portfolio](账户对象/Portfolio.md) - 账户对象
- [SubPortfolio](账户对象/SubPortfolio.md) - 子账户对象
- [Position](账户对象/Position.md) - 持仓对象
- [Order](账户对象/Order.md) - 订单对象
- [Trade](账户对象/Trade.md) - 成交对象

### 期货交易
- [get_dominant_future](期货交易/get_dominant_future.md) - 获取主力合约
- [get_future_contracts](期货交易/get_future_contracts.md) - 获取期货合约列表
- [期货下单函数](期货交易/期货下单函数.md) - 期货专用下单函数
- [期货保证金设置](期货交易/期货保证金设置.md) - 保证金和手续费设置

### 融资融券
- [融资融券初始化](融资融券/融资融券初始化.md) - 启用融资融券
- [margincash_open](融资融券/margincash_open.md) - 融资开仓
- [margincash_close](融资融券/margincash_close.md) - 融资平仓
- [marginsec_open](融资融券/marginsec_open.md) - 融券开仓
- [marginsec_close](融资融券/marginsec_close.md) - 融券平仓
- [get_margincash_stocks](融资融券/get_margincash_stocks.md) - 获取融资标的
- [get_marginsec_stocks](融资融券/get_marginsec_stocks.md) - 获取融券标的
- [get_mtss](融资融券/get_mtss.md) - 获取融资融券数据

### 投资组合优化
- [portfolio_optimizer](投资组合优化/portfolio_optimizer.md) - 组合优化器
- [优化目标函数](投资组合优化/优化目标函数.md) - 目标函数详解
- [限制函数](投资组合优化/限制函数.md) - 约束条件详解
- [边界函数](投资组合优化/边界函数.md) - 权重边界详解

### Tick数据
- [handle_tick](Tick数据/handle_tick.md) - Tick数据处理
- [subscribe](Tick数据/subscribe.md) - 订阅Tick数据
- [unsubscribe](Tick数据/unsubscribe.md) - 取消订阅
- [get_current_tick](Tick数据/get_current_tick.md) - 获取当前Tick

### 工具函数
- [get_orders](工具函数/get_orders.md) - 获取订单记录
- [get_trades](工具函数/get_trades.md) - 获取成交记录
- [send_message](工具函数/send_message.md) - 发送消息
- [record](工具函数/record.md) - 记录指标
- [log](工具函数/log.md) - 日志输出
- [write_file](工具函数/write_file.md) - 写入文件
- [read_file](工具函数/read_file.md) - 读取文件

### 策略函数
- [initialize](策略函数/initialize.md) - 初始化函数
- [handle_data](策略函数/handle_data.md) - 数据处理函数
- [before_trading_start](策略函数/before_trading_start.md) - 开盘前运行
- [after_trading_end](策略函数/after_trading_end.md) - 收盘后运行
- [run_daily](策略函数/run_daily.md) - 按日运行
- [run_monthly](策略函数/run_monthly.md) - 按月运行

### 配置函数
- [set_benchmark](配置函数/set_benchmark.md) - 设置基准
- [set_option](配置函数/set_option.md) - 设置选项
- [set_order_cost](配置函数/set_order_cost.md) - 设置手续费
- [set_universe](配置函数/set_universe.md) - 设置股票池

### 实用函数
- [normalize_code](实用函数/normalize_code.md) - 标准化证券代码
- [get_trade_days](实用函数/get_trade_days.md) - 获取交易日

## 使用说明

每个API文档包含以下内容:
- **函数签名**: 完整的函数调用方式
- **参数说明**: 各参数的含义和类型
- **返回值**: 返回值的类型和说明
- **使用示例**: 实际代码示例
- **注意事项**: 重要的提醒和限制

## 相关资源

- 聚宽官网: https://www.joinquant.com/
- 聚宽社区: https://www.joinquant.com/community/
- 原始文档: 聚宽接口文档.md

## 更新日期

2026-02-28
