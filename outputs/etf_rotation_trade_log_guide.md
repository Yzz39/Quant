ETF动量轮动交易日志模板使用说明

定位：这是研究和纸面交易日志，不是实盘交易建议。

一、每次交易至少填什么

最少要填 trade_log 里的这些字段：

1. trade_id：交易编号。
2. strategy_version：策略版本。
3. trade_stage：阶段，建议先用 paper_trade。
4. trade_date：纸面执行日期。
5. signal_date：信号生成日期。
6. symbol / asset_name：ETF代码和名称。
7. action：BUY、SELL、HOLD、SKIP或REBALANCE。
8. risk_state：risk_on、defensive或cash。
9. target_weight_after：交易后目标权重。
10. paper_price、paper_quantity、estimated_cost：纸面成交记录和成本。
11. nav_before、nav_after：纸面账户净值变化。
12. manual_override：是否人工覆盖信号。
13. review_note：盘后备注。

二、推荐填写顺序

1. signal_snapshot：先记录信号来源和排名。
2. trade_log：记录本次交易主表。
3. order_log：如果有买卖动作，记录模拟订单。
4. portfolio_snapshot：更新交易后持仓。
5. nav_daily：每天或每周更新净值。
6. weekly_review：每周末复盘。
7. exception_log：记录异常、缺失数据、人工覆盖等问题。

三、纸面交易纪律

1. 纸面交易也要扣成本。
2. 不允许事后改信号日期。
3. 不允许因为涨跌随意改规则。
4. 人工覆盖可以记录，但必须写原因。
5. 如果数据缺失或价格异常，默认不交易。

四、关键判断

交易日志不是为了证明自己对了，而是为了保留证据。
连续12周后，用这些日志计算：

- 总收益
- 相对510300超额收益
- 最大回撤
- 信号执行率
- 人工覆盖次数
- 规则修改次数
- 情绪压力

然后再决定：继续研究、纸面交易强化，还是暂缓。

文件：

- D:/Quant/outputs/etf_rotation_trade_log_template.xlsx
- D:/Quant/outputs/etf_rotation_trade_log_template.csv
- D:/Quant/outputs/etf_rotation_trade_log_guide.md
