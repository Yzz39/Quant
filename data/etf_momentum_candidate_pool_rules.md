# ETF 动量候选池筛选规则

源文件：`etf_momentum_daily_eastmoney_qfq.csv`

生成文件：

- `etf_momentum_candidate_pool.csv`：完整候选池与筛选理由
- `etf_momentum_candidate_pool_selected.csv`：当前纳入候选池的 ETF

## 字段含义

- `symbol`：ETF 代码
- `name`：ETF 名称
- `bucket`：原始分组，例如 `benchmark`、`defensive`、`sector`
- `theme`：主题或跟踪方向
- `role`：策略中的角色
  - `benchmark`：宽基基准/对照组
  - `defensive_asset`：防御资产/避险腿
  - `sector_rotation`：行业/主题轮动候选
- `candidate_status`：筛选状态
  - `selected`：纳入当前候选池
  - `watchlist`：暂不正式纳入，后续观察
  - `excluded`：排除
- `first_date` / `last_date`：该 ETF 在源数据中的首末日期
- `history_years`：可用历史年限
- `avg_amount_60d`：最近 60 条交易记录的平均成交额
- `latest_amount`：最新一条记录的成交额
- `missing_close_count_long`：原始长表中的 close 缺失条数
- `screening_reason`：纳入、观察或排除理由

## 当前筛选口径

行业/主题 ETF 纳入条件：

1. 可用历史长度不少于 3 年；
2. 最近 60 条交易记录平均成交额不低于 1 亿元；
3. 最新日期与全表最新日期一致；
4. `bucket` 可以识别为 `sector`。

宽基 ETF：作为 benchmark 纳入，用于策略对照，不建议和行业主题 ETF 混在同一个排名池中直接竞争。

国债 ETF：作为 defensive_asset 纳入，可用于股债切换、防御仓位或空仓替代，不建议和行业主题 ETF 混在同一个排名池中直接竞争。

## 注意事项

- 候选池不是永久名单，应该随数据更新、流动性变化、ETF 规模变化定期重建。
- 上市较晚导致的宽表历史缺失，不一定是数据错误；应结合 `first_date` 判断。
- 后续正式回测时，建议先只对 `role = sector_rotation` 的 ETF 做行业主题动量排名，再把 benchmark/defensive_asset 作为对照或风险控制资产。
