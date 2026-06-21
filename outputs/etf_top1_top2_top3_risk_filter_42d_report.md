# Top1/Top2/Top3 42日动量风险过滤 vectorbt 对比报告

## 规则

- 动量窗口：`42` 个交易日。
- 调仓频率：`monthly`，调仓日收盘后生成信号，下一交易日目标权重生效。
- 风险过滤：若行业/主题 ETF 存在正动量，则选择 TopN 正动量标的等权持有。
- 若行业/主题 ETF 均无正动量，则切换到正动量防守资产；若防守资产也无正动量，则空仓。
- vectorbt 成本：佣金 `0.0100%`，滑点 `0.0100%`。

## 同窗口对比

| version | total_return | annualized_return | annualized_volatility | max_drawdown | sharpe_like_no_rf | order_count | cash_target_days | defensive_signals | cash_signals |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 原 Top1 42日 | 15.077991 | 0.285950 | 0.377056 | -0.472823 | 0.856003 | 159 | 57 |  |  |
| 原 Top2 42日 | 7.069699 | 0.208136 | 0.303575 | -0.460581 | 0.775043 | 4155 | 57 |  |  |
| 原 Top3 42日 | 2.768648 | 0.127648 | 0.283969 | -0.497862 | 0.565586 | 5686 | 57 |  |  |
| 风险过滤 Top1 42日 | 15.077991 | 0.285950 | 0.377056 | -0.472823 | 0.856003 | 159 | 57 | 6.000000 | 2.000000 |
| 风险过滤 Top2 42日 | 7.069699 | 0.208136 | 0.303575 | -0.460581 | 0.775043 | 4155 | 57 | 6.000000 | 2.000000 |
| 风险过滤 Top3 42日 | 2.768648 | 0.127648 | 0.283969 | -0.497862 | 0.565586 | 5686 | 57 | 6.000000 | 2.000000 |

## 输出文件

- 风险过滤汇总指标：`D:/Quant/outputs/etf_top1_top2_top3_risk_filter_42d_vectorbt_metrics.csv`
- 与原始 Top1/Top2/Top3 对比：`D:/Quant/outputs/etf_top1_top2_top3_risk_filter_42d_comparison.csv`

## 风险过滤 Top1 最新信号

- 信号日：2026-06-18
- 风险状态：`risk_on`
- 选择：`512480` 半导体ETF国联安
- 单只目标权重：100.00%
- 年化收益：28.59%
- 最大回撤：-47.28%
- 每日净值：`D:/Quant/outputs/etf_top1_risk_filter_42d_vectorbt_daily_value.csv`
- 目标权重：`D:/Quant/outputs/etf_top1_risk_filter_42d_vectorbt_target_weights.csv`
- 调仓决策：`D:/Quant/outputs/etf_top1_risk_filter_42d_vectorbt_decisions.csv`
- 订单明细：`D:/Quant/outputs/etf_top1_risk_filter_42d_vectorbt_orders.csv`
- 指标：`D:/Quant/outputs/etf_top1_risk_filter_42d_vectorbt_metrics.csv`

## 风险过滤 Top2 最新信号

- 信号日：2026-06-18
- 风险状态：`risk_on`
- 选择：`512480` 半导体ETF国联安
- 单只目标权重：100.00%
- 年化收益：20.81%
- 最大回撤：-46.06%
- 每日净值：`D:/Quant/outputs/etf_top2_risk_filter_42d_vectorbt_daily_value.csv`
- 目标权重：`D:/Quant/outputs/etf_top2_risk_filter_42d_vectorbt_target_weights.csv`
- 调仓决策：`D:/Quant/outputs/etf_top2_risk_filter_42d_vectorbt_decisions.csv`
- 订单明细：`D:/Quant/outputs/etf_top2_risk_filter_42d_vectorbt_orders.csv`
- 指标：`D:/Quant/outputs/etf_top2_risk_filter_42d_vectorbt_metrics.csv`

## 风险过滤 Top3 最新信号

- 信号日：2026-06-18
- 风险状态：`risk_on`
- 选择：`512480` 半导体ETF国联安
- 单只目标权重：100.00%
- 年化收益：12.76%
- 最大回撤：-49.79%
- 每日净值：`D:/Quant/outputs/etf_top3_risk_filter_42d_vectorbt_daily_value.csv`
- 目标权重：`D:/Quant/outputs/etf_top3_risk_filter_42d_vectorbt_target_weights.csv`
- 调仓决策：`D:/Quant/outputs/etf_top3_risk_filter_42d_vectorbt_decisions.csv`
- 订单明细：`D:/Quant/outputs/etf_top3_risk_filter_42d_vectorbt_orders.csv`
- 指标：`D:/Quant/outputs/etf_top3_risk_filter_42d_vectorbt_metrics.csv`
