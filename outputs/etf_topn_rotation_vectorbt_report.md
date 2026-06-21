# vectorbt Top2/Top3 等权 ETF 轮动回测报告

## 规则

- 动量窗口：`42` 个交易日。
- 调仓频率：`monthly`，调仓日收盘后生成信号，下一交易日目标权重生效。
- 行业/主题 ETF 中选择动量为正的 Top2 或 Top3。
- 入选行业/主题 ETF 等权持有；若不足 N 只正动量 ETF，则只等权持有实际入选标的。
- 若行业/主题 ETF 均无正动量，则切换到正动量防守资产；若防守资产也无正动量，则空仓。
- vectorbt 成本：佣金 `0.0100%`，滑点 `0.0100%`。

## 汇总指标

| name | top_n | lookback_days | rebalance_frequency | init_cash | fee_rate | slippage | total_return | annualized_return | annualized_volatility | max_drawdown | sharpe_like_no_rf | final_value | order_count | total_fees | total_order_value | annual_traded_value_ratio | cash_target_days | single_asset_target_days | multi_asset_target_days |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vectorbt_top2_equal_weight_rotation | 2 | 42 | monthly | 100000.000000 | 0.000100 | 0.000100 | 7.069699 | 0.208136 | 0.303575 | -0.460581 | 0.775043 | 806969.892436 | 4155 | 5215.796200 | 52157961.999347 | 47.228913 | 57 | 402 | 2324 |
| vectorbt_top3_equal_weight_rotation | 3 | 42 | monthly | 100000.000000 | 0.000100 | 0.000100 | 2.768648 | 0.127648 | 0.283969 | -0.497862 | 0.565586 | 376864.810595 | 5686 | 3378.697306 | 33786973.059605 | 30.594025 | 57 | 402 | 2324 |
| buy_hold_510300 | 0 | 0 | buy_hold | 100000.000000 | 0.000000 | 0.000000 | 0.725164 | 0.050618 | 0.265148 | -0.529723 | 0.319770 | 172516.441675 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 | 2783 | 0 |

## 输出文件

- 汇总指标：`D:/Quant/outputs/etf_topn_rotation_vectorbt_metrics.csv`

## Top2 最新信号与文件

- 信号日：2026-06-18
- 选择：`512480` 半导体ETF国联安
- 单只目标权重：100.00%
- 总收益：706.97%
- 年化收益：20.81%
- 最大回撤：-46.06%
- 类夏普：0.78
- 订单行数：4155
- 每日净值：`D:/Quant/outputs/etf_top2_equal_weight_rotation_vectorbt_daily_value.csv`
- 目标权重：`D:/Quant/outputs/etf_top2_equal_weight_rotation_vectorbt_target_weights.csv`
- 调仓决策：`D:/Quant/outputs/etf_top2_equal_weight_rotation_vectorbt_decisions.csv`
- 订单明细：`D:/Quant/outputs/etf_top2_equal_weight_rotation_vectorbt_orders.csv`
- 指标：`D:/Quant/outputs/etf_top2_equal_weight_rotation_vectorbt_metrics.csv`

## Top3 最新信号与文件

- 信号日：2026-06-18
- 选择：`512480` 半导体ETF国联安
- 单只目标权重：100.00%
- 总收益：276.86%
- 年化收益：12.76%
- 最大回撤：-49.79%
- 类夏普：0.57
- 订单行数：5686
- 每日净值：`D:/Quant/outputs/etf_top3_equal_weight_rotation_vectorbt_daily_value.csv`
- 目标权重：`D:/Quant/outputs/etf_top3_equal_weight_rotation_vectorbt_target_weights.csv`
- 调仓决策：`D:/Quant/outputs/etf_top3_equal_weight_rotation_vectorbt_decisions.csv`
- 订单明细：`D:/Quant/outputs/etf_top3_equal_weight_rotation_vectorbt_orders.csv`
- 指标：`D:/Quant/outputs/etf_top3_equal_weight_rotation_vectorbt_metrics.csv`
