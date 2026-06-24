# bt 组合回测最小版本报告

## 定位

这是一个不依赖 vectorbt 的最小 pandas 组合回测，用来理解组合权重、再平衡、成本和净值的基本关系。

## 规则

- 数据：`D:/Quant/data/etf_momentum_daily_eastmoney_qfq.csv`。
- 动量：`close / close.shift(42) - 1`。
- 调仓：每月最后一个交易日收盘后生成信号，下一交易日开始持有目标权重。
- 组合：行业/主题 ETF 正动量 Top2/Top3 等权；无正动量行业 ETF 时切防守资产；否则空仓。
- 成本：单边佣金 `0.0100%` + 滑点 `0.0100%`，按单边换手扣除。

## 汇总指标

| name | top_n | lookback_days | rebalance_frequency | init_cash | one_way_cost_rate | total_return | annualized_return | annualized_volatility | max_drawdown | sharpe_like_no_rf | final_value | trade_day_count | total_one_way_turnover | annual_one_way_turnover | total_cost_drag | cash_target_days |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bt_minimal_top2_equal_weight | 2 | 42 | monthly | 100000.000000 | 0.000200 | 7.290477 | 0.211092 | 0.304989 | -0.461141 | 0.780888 | 829047.708168 | 97 | 65.500000 | 5.931010 | 0.013100 | 57 |
| bt_minimal_top3_equal_weight | 3 | 42 | monthly | 100000.000000 | 0.000200 | 3.001324 | 0.133782 | 0.285294 | -0.498608 | 0.583313 | 400132.356522 | 108 | 68.000000 | 6.157384 | 0.013600 | 57 |
| buy_hold_510300 | 0 | 0 | buy_hold | 100000.000000 | 0.000000 | 0.725164 | 0.050618 | 0.265148 | -0.529723 | 0.319770 | 172516.441675 | 0 | 0.000000 | 0.000000 | 0.000000 | 0 |

## 最新信号

- Top2：2026-06-18，`512480`，半导体ETF国联安，原因：选择正动量行业/主题 ETF Top2，等权持有
- Top3：2026-06-18，`512480`，半导体ETF国联安，原因：选择正动量行业/主题 ETF Top3，等权持有
