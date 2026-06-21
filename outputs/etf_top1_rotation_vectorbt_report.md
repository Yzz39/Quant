# vectorbt Top1 ETF 轮动回测报告

## 规则

- 动量窗口：`42` 个交易日。
- 调仓频率：`monthly`，调仓日收盘后生成信号，下一交易日目标权重生效。
- 行业/主题 ETF 中选择动量最高的 Top1。
- 若 Top1 行业/主题 ETF 动量为负或不可用，则切换到正动量防守资产；若防守资产也无正动量，则空仓。
- vectorbt 成本：佣金 `0.0100%`，滑点 `0.0100%`。

## 输出文件

- 每日净值：`D:/Quant/outputs/etf_top1_rotation_vectorbt_daily_value.csv`
- 目标权重：`D:/Quant/outputs/etf_top1_rotation_vectorbt_target_weights.csv`
- 调仓决策：`D:/Quant/outputs/etf_top1_rotation_vectorbt_decisions.csv`
- 订单明细：`D:/Quant/outputs/etf_top1_rotation_vectorbt_orders.csv`
- 指标：`D:/Quant/outputs/etf_top1_rotation_vectorbt_metrics.csv`

## 关键结果

- 总收益：1507.80%
- 年化收益：28.59%
- 最大回撤：-47.28%
- 类夏普：0.86
- 最终资产：1,607,799.05
- 订单数：159
- 总手续费：9,460.05
- 年化成交额/初始本金：85.66x

## 最新信号

- 信号日：2026-06-18
- 选择：`512480` 半导体ETF国联安
- 类型：sector
- 动量：53.15%
- 理由：Top1 行业/主题 ETF 动量为正，持有该 ETF

## 订单摘要

- 订单行数：159
