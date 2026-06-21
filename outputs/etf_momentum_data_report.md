# ETF 动量轮动历史价格数据下载报告

## 数据文件

- 价格数据：`D:/Quant/data/etf_momentum_daily_eastmoney_qfq.csv`
- 候选池元数据：`D:/Quant/data/etf_momentum_universe.csv`

## 复权口径确认

- 数据源：东方财富 push2his K 线接口。
- 接口参数：`klt=101` 日线，`fqt=1`。
- 项目口径：`adjust=qfq`，即前复权。
- 用途：用于收益率、动量排序、均线等历史价格计算。
- 注意：ETF 通常无印花税；复权用于处理分红等造成的价格跳变，但仍应在正式回测前做异常值检查。

## 候选池分层

- `sector`：行业/板块轮动主池。
- `defensive`：国债、货币、黄金等防御资产。
- `benchmark`：宽基基准，用于对照或市场状态过滤，不作为板块轮动主角。

## 下载概况

- 成功 ETF 数：18
- 总行数：37957
- 样本起始：2015-01-05
- 样本结束：2026-06-18

## 下载失败

- `159995` 芯片ETF：Failed to download 0.159995: Remote end closed connection without response; curl fallback: Command '['curl', '-L', '--max-time', '45', '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', '-H', 'Referer: https://quote.eastmoney.com/', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.159995&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61&klt=101&fqt=1&beg=20150101&end=20500101']' returned non-zero exit status 56.
- `159819` 人工智能ETF：Failed to download 0.159819: Remote end closed connection without response; curl fallback: Command '['curl', '-L', '--max-time', '45', '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', '-H', 'Referer: https://quote.eastmoney.com/', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.159819&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61&klt=101&fqt=1&beg=20150101&end=20500101']' returned non-zero exit status 56.
- `159996` 家电ETF：Failed to download 0.159996: Remote end closed connection without response; curl fallback: Command '['curl', '-L', '--max-time', '45', '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', '-H', 'Referer: https://quote.eastmoney.com/', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.159996&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61&klt=101&fqt=1&beg=20150101&end=20500101']' returned non-zero exit status 56.
- `159865` 养殖ETF：Failed to download 0.159865: Remote end closed connection without response; curl fallback: Command '['curl', '-L', '--max-time', '45', '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', '-H', 'Referer: https://quote.eastmoney.com/', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.159865&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61&klt=101&fqt=1&beg=20150101&end=20500101']' returned non-zero exit status 56.
- `159825` 农业ETF：Failed to download 0.159825: Remote end closed connection without response; curl fallback: Command '['curl', '-L', '--max-time', '45', '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', '-H', 'Referer: https://quote.eastmoney.com/', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.159825&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61&klt=101&fqt=1&beg=20150101&end=20500101']' returned non-zero exit status 56.
- `511880` 银华日利ETF：Failed to download 1.511880: Remote end closed connection without response; curl fallback: Command '['curl', '-L', '--max-time', '45', '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', '-H', 'Referer: https://quote.eastmoney.com/', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.511880&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61&klt=101&fqt=1&beg=20150101&end=20500101']' returned non-zero exit status 56.
- `518880` 黄金ETF：Failed to download 1.518880: Remote end closed connection without response; curl fallback: Command '['curl', '-L', '--max-time', '45', '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', '-H', 'Referer: https://quote.eastmoney.com/', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.518880&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61&klt=101&fqt=1&beg=20150101&end=20500101']' returned non-zero exit status 56.
- `510500` 中证500ETF：Failed to download 1.510500: Remote end closed connection without response; curl fallback: Command '['curl', '-L', '--max-time', '45', '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', '-H', 'Referer: https://quote.eastmoney.com/', 'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.510500&fields1=f1%2Cf2%2Cf3%2Cf4%2Cf5%2Cf6&fields2=f51%2Cf52%2Cf53%2Cf54%2Cf55%2Cf56%2Cf57%2Cf58%2Cf59%2Cf60%2Cf61&klt=101&fqt=1&beg=20150101&end=20500101']' returned non-zero exit status 56.

## 单品种数据摘要

| 分层 | 代码 | 名称 | 主题 | 行数 | 起始 | 结束 | 首日收盘 | 末日收盘 | 平均成交额 | 最低成交额 | 缺失收盘 |
|---|---|---|---|---:|---|---|---:|---:|---:|---:|---:|
| benchmark | 159915 | 创业板ETF易方达 | 创业板 | 2782 | 2015-01-05 | 2026-06-18 | 1.4240 | 4.2690 | 1,456,465,621 | 63,329,683 | 0 |
| benchmark | 510300 | 沪深300ETF华泰柏瑞 | 沪深300 | 2783 | 2015-01-05 | 2026-06-18 | 2.8890 | 4.9840 | 2,428,533,179 | 155,394,118 | 0 |
| defensive | 511010 | 国债ETF国泰 | 国债 | 2783 | 2015-01-05 | 2026-06-18 | 99.6200 | 141.4310 | 385,025,365 | 2,408,301 | 0 |
| defensive | 511260 | 十年国债ETF国泰 | 十年国债 | 2137 | 2017-08-24 | 2026-06-18 | 96.6230 | 135.9840 | 768,977,769 | 24,384 | 0 |
| sector | 159928 | 消费ETF汇添富 | 消费 | 2783 | 2015-01-05 | 2026-06-18 | 0.3000 | 0.6230 | 136,604,145 | 5,731 | 0 |
| sector | 512010 | 医药ETF易方达 | 医药 | 2781 | 2015-01-05 | 2026-06-18 | 0.2570 | 0.3260 | 251,947,494 | 786 | 0 |
| sector | 512170 | 医疗ETF华宝 | 医疗 | 1699 | 2019-06-17 | 2026-06-18 | 0.3280 | 0.2960 | 389,045,096 | 2,479,580 | 0 |
| sector | 512400 | 有色金属ETF南方 | 有色金属 | 2132 | 2017-09-01 | 2026-06-18 | 1.0110 | 2.0500 | 252,134,747 | 113,306 | 0 |
| sector | 512480 | 半导体ETF国联安 | 半导体 | 1702 | 2019-06-12 | 2026-06-18 | 0.5070 | 2.4810 | 882,621,523 | 3,717,624 | 0 |
| sector | 512660 | 军工ETF国泰 | 军工 | 2393 | 2016-08-08 | 2026-06-18 | 1.0170 | 1.2900 | 368,585,129 | 5,945,786 | 0 |
| sector | 512690 | 酒ETF鹏华 | 白酒/酒 | 1728 | 2019-05-06 | 2026-06-18 | 0.1040 | 0.4040 | 513,531,821 | 7,449,087 | 0 |
| sector | 512800 | 银行ETF华宝 | 银行 | 2153 | 2017-08-03 | 2026-06-18 | 0.5000 | 0.7660 | 316,834,076 | 1,590,339 | 0 |
| sector | 512880 | 证券ETF国泰 | 证券 | 2393 | 2016-08-08 | 2026-06-18 | 1.0040 | 1.0500 | 1,155,727,523 | 2,458,331 | 0 |
| sector | 512980 | 传媒ETF广发 | 传媒 | 2038 | 2018-01-19 | 2026-06-18 | 1.0010 | 0.8270 | 111,386,516 | 1,178,057 | 0 |
| sector | 515030 | 新能源车ETF华夏 | 新能源车 | 1526 | 2020-03-04 | 2026-06-18 | 0.9790 | 1.9250 | 300,929,128 | 32,847,670 | 0 |
| sector | 515220 | 煤炭ETF国泰 | 煤炭 | 1528 | 2020-03-02 | 2026-06-18 | 0.3330 | 1.1560 | 290,787,993 | 11,626,770 | 0 |
| sector | 515230 | 软件ETF国泰 | 软件 | 1285 | 2021-03-02 | 2026-06-18 | 0.9670 | 0.7240 | 99,501,142 | 16,596,577 | 0 |
| sector | 515790 | 光伏ETF华泰柏瑞 | 光伏 | 1331 | 2020-12-18 | 2026-06-18 | 1.0310 | 1.0170 | 632,141,473 | 119,828,429 | 0 |
