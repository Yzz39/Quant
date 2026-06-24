bt / vectorbt 等权组合回测：未来函数与成本假设检查

一、检查对象

核心脚本：D:\Quant\scripts\vectorbt_topn_etf_rotation.py
策略：Top2 / Top3 等权 ETF 动量轮动。
数据：D:/Quant/data/etf_momentum_daily_eastmoney_qfq.csv。

二、未来函数检查结论

未发现明显同日偷看未来执行，但存在一个需要注意的实现口径：信号用月末收盘价计算，目标权重从下一交易日才生效。代码实现与报告描述基本一致。

关键代码逻辑：

1. 动量计算：momentum = close / close.shift(LOOKBACK_DAYS) - 1.0。
   这只使用当前信号日及其42个交易日前的价格，没有使用未来价格。

2. 信号日期：signal_dates 使用每月最后一个交易日。
   信号在月末收盘后才能知道，因此不能在同一天收盘价成交。

3. 权重生效：target_weights 循环中先写入旧持仓，再在 signal_date 更新 current_symbols。
   结果是：signal_date 当天仍保持旧权重，新的目标权重从下一条交易日开始生效。
   这避免了“用当天收盘价算信号，同时当天收盘价成交”的同日未来函数。

4. 仍需注意：当前成交价格使用下一交易日的 close，而不是 next open。
   这不是典型未来函数，但它是假设你能在下一交易日收盘价附近执行。若真实操作在开盘或盘中，应另做 next_open 或 VWAP 假设版本。

三、成本假设检查结论

成本假设为佣金0.01% + 滑点0.01%，单边合计0.02%，双边约0.04%。这对高流动性ETF偏乐观但可作为研究基线；进入纸面交易前建议增加0.05%、0.10%、0.20%单边压力测试。

当前脚本参数：

- FEE_RATE = 0.0001，即 0.01%。
- SLIPPAGE = 0.0001，即 0.01%。
- 单边总摩擦约 0.02%。
- 一买一卖双边摩擦约 0.04%。

这对流动性好的宽基/行业ETF可能可以作为乐观研究基线；但对成交额较低、冲击成本较高或实盘资金变大时，偏乐观。

四、量化检查摘要

 top_n  checked_recent_signals  same_day_selected_weight_count  next_day_match_count  fee_rate  slippage  one_way_cost_assumption  round_trip_cost_assumption  orders  total_order_value  total_fees_from_orders  implied_fee_rate_from_orders  annual_traded_value_ratio  total_return  max_drawdown
     2                      59                              40                    59    0.0001    0.0001                   0.0002                      0.0004    4155       5.215796e+07             5215.796200                        0.0001                  47.228913      7.069699     -0.460581
     3                      59                              47                    59    0.0001    0.0001                   0.0002                      0.0004    5686       3.378697e+07             3378.697306                        0.0001                  30.594025      2.768648     -0.497862

五、风险判断

1. 未来函数风险：低到中。核心信号/执行错位是合理的，但执行价用下一日收盘价，需要在报告中明确。
2. 成本假设风险：中。当前成本偏研究基线，不能直接当实盘成本。
3. 最大风险：如果未来改代码时把 target_weights 的更新顺序改成先更新再写入同日权重，就会变成同日收盘信号同日成交，产生未来函数。

六、建议下一步

1. 保留当前版本作为“next close execution”研究基线。
2. 新增更保守版本：next open 或 next close + 更高滑点。
3. 做成本压力测试：单边总成本 0.05%、0.10%、0.20%。
4. 在策略报告中明确：信号月末收盘后生成，下一交易日执行。
5. 写一个单元测试，锁定“信号日当天不能持有新信号权重”。
