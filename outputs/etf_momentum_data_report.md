# ETF 动量轮动历史价格数据下载报告

## 输出文件

- 价格数据：`D:/Quant/data/etf_momentum_daily_eastmoney_qfq.csv`
- 候选池元数据：`D:/Quant/data/etf_momentum_universe.csv`
- 数据质量摘要：`D:/Quant/outputs/etf_momentum_data_quality.csv`

## 复权口径确认

- 数据源：东方财富 push2his K线接口，以及项目已有同源历史文件补入。
- 接口参数：`klt=101` 日线，`fqt=1`。
- 项目记录口径：`adjust=qfq`，即前复权。
- 价格字段 `open/high/low/close` 按该前复权口径保存；成交量、成交额为接口返回值。
- 用途：适合计算 ETF 历史收益率、动量排序、均线；正式回测前仍应进行异常值和流动性过滤。

## 候选池说明

- `sector`：行业/板块 ETF，作为动量轮动主池。
- `defensive`：国债、货币、黄金等防御资产。
- `benchmark`：宽基 ETF，用于对照或市场状态过滤。

## 下载结果概况

- 计划 ETF 数：26
- 成功 ETF 数：16
- 失败 ETF 数：10
- 总行数：33037
- 数据起始：2015-01-05
- 数据结束：2026-06-18

## 未获取成功的品种

- `510500` 中证500ETF（benchmark/中证500）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。
- `511260` 十年国债ETF（defensive/十年国债）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。
- `511880` 银华日利ETF（defensive/货币/现金）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。
- `518880` 黄金ETF（defensive/黄金）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。
- `159819` 人工智能ETF（sector/人工智能）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。
- `159825` 农业ETF（sector/农业）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。
- `159865` 养殖ETF（sector/养殖）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。
- `159928` 消费ETF（sector/消费）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。
- `159995` 芯片ETF（sector/芯片）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。
- `159996` 家电ETF（sector/家电）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。

## 单品种质量摘要

| 状态 | 分层 | 代码 | 计划名称 | 实际名称 | 主题 | 行数 | 起始 | 结束 | 平均成交额 | 最低成交额 | 复权 | 来源 |
|---|---|---|---|---|---|---:|---|---|---:|---:|---|---|
| ok | benchmark | 159915 | 创业板ETF | 创业板ETF易方达 | 创业板 | 2782 | 2015-01-05 | 2026-06-18 | 1,456,465,621 | 63,329,683 | qfq | eastmoney_push2his_existing_project_file |
| ok | benchmark | 510300 | 沪深300ETF | 沪深300ETF华泰柏瑞 | 沪深300 | 2783 | 2015-01-05 | 2026-06-18 | 2,428,533,179 | 155,394,118 | qfq | eastmoney_push2his_existing_project_file |
| failed | benchmark | 510500 | 中证500ETF |  | 中证500 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| ok | defensive | 511010 | 国债ETF | 国债ETF国泰 | 国债 | 2783 | 2015-01-05 | 2026-06-18 | 385,025,365 | 2,408,301 | qfq | eastmoney_push2his_existing_project_file |
| failed | defensive | 511260 | 十年国债ETF |  | 十年国债 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| failed | defensive | 511880 | 银华日利ETF |  | 货币/现金 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| failed | defensive | 518880 | 黄金ETF |  | 黄金 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| failed | sector | 159819 | 人工智能ETF |  | 人工智能 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| failed | sector | 159825 | 农业ETF |  | 农业 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| failed | sector | 159865 | 养殖ETF |  | 养殖 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| failed | sector | 159928 | 消费ETF |  | 消费 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| failed | sector | 159995 | 芯片ETF |  | 芯片 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| failed | sector | 159996 | 家电ETF |  | 家电 | 0 |  |  | 0 | 0 | qfq_planned_not_downloaded | eastmoney_push2his_failed |
| ok | sector | 512010 | 医药ETF | 医药ETF易方达 | 医药 | 2781 | 2015-01-05 | 2026-06-18 | 251,947,494 | 786 | qfq | eastmoney_push2his |
| ok | sector | 512170 | 医疗ETF | 医疗ETF华宝 | 医疗 | 1699 | 2019-06-17 | 2026-06-18 | 389,045,096 | 2,479,580 | qfq | eastmoney_push2his |
| ok | sector | 512400 | 有色金属ETF | 有色金属ETF南方 | 有色金属 | 2132 | 2017-09-01 | 2026-06-18 | 252,134,747 | 113,306 | qfq | eastmoney_push2his |
| ok | sector | 512480 | 半导体ETF | 半导体ETF国联安 | 半导体 | 1702 | 2019-06-12 | 2026-06-18 | 882,621,523 | 3,717,624 | qfq | eastmoney_push2his |
| ok | sector | 512660 | 军工ETF | 军工ETF国泰 | 军工 | 2393 | 2016-08-08 | 2026-06-18 | 368,585,129 | 5,945,786 | qfq | eastmoney_push2his |
| ok | sector | 512690 | 酒ETF | 酒ETF鹏华 | 白酒/酒 | 1728 | 2019-05-06 | 2026-06-18 | 513,531,821 | 7,449,087 | qfq | eastmoney_push2his |
| ok | sector | 512800 | 银行ETF | 银行ETF华宝 | 银行 | 2153 | 2017-08-03 | 2026-06-18 | 316,834,076 | 1,590,339 | qfq | eastmoney_push2his |
| ok | sector | 512880 | 证券ETF | 证券ETF国泰 | 证券 | 2393 | 2016-08-08 | 2026-06-18 | 1,155,727,523 | 2,458,331 | qfq | eastmoney_push2his |
| ok | sector | 512980 | 传媒ETF | 传媒ETF广发 | 传媒 | 2038 | 2018-01-19 | 2026-06-18 | 111,386,516 | 1,178,057 | qfq | eastmoney_push2his |
| ok | sector | 515030 | 新能源车ETF | 新能源车ETF华夏 | 新能源车 | 1526 | 2020-03-04 | 2026-06-18 | 300,929,128 | 32,847,670 | qfq | eastmoney_push2his |
| ok | sector | 515220 | 煤炭ETF | 煤炭ETF国泰 | 煤炭 | 1528 | 2020-03-02 | 2026-06-18 | 290,787,993 | 11,626,770 | qfq | eastmoney_push2his |
| ok | sector | 515230 | 软件ETF | 软件ETF国泰 | 软件 | 1285 | 2021-03-02 | 2026-06-18 | 99,501,142 | 16,596,577 | qfq | eastmoney_push2his |
| ok | sector | 515790 | 光伏ETF | 光伏ETF华泰柏瑞 | 光伏 | 1331 | 2020-12-18 | 2026-06-18 | 632,141,473 | 119,828,429 | qfq | eastmoney_push2his |
