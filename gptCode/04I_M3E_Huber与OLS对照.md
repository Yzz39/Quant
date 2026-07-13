# 04I：M3E Huber与OLS对照

## 状态

- 当前版本：v0.3-result1
- 当前状态：Huber组合结果已取得；最终标签和同引擎OLS对照缺失
- 研究问题：Huber稳健斜率是否优于等权OLS斜率
- M3E模式：`RUN_MODE = "m3e_huber_slope"`
- OLS对照模式：`RUN_MODE = "m3_ols_slope"`

本实验检验Huber是否强于OLS，不预设Huber必然更强。若未达到下述门槛，结论必须是“不支持Huber优于OLS”。

## 一、唯一变化

两组都使用127个前复权收盘价的log价格、相同的0至126时间轴、月末信号、21日近期确认、Top1、相同候选池和v0.9执行引擎。

| 项目 | OLS对照 | M3E Huber |
|---|---|---|
| 回归损失 | 平方损失 | Huber损失 |
| 残差尺度 | 不需要 | MAD / 0.67448975 |
| epsilon | 不适用 | 1.345 |
| 求解 | 闭式OLS | IRLS，最多50次 |
| 收敛阈值 | 不适用 | 截距或斜率最大变化不超过1e-10 |
| 正则化 | 无 | 无 |
| 拟合质量 | 标准R2 | 最终Huber权重下的加权R2 |
| 得分 | beta_ols * R2_ols | beta_huber * R2_huber |

Huber权重定义：

```text
scale = MAD(residual) / 0.67448975
threshold = 1.345 * scale
w_i = 1                              if abs(residual_i) <= threshold
w_i = threshold / abs(residual_i)    otherwise
```

不得扫描epsilon、迭代次数、窗口或R2定义。参数变化必须建立新版本。

## 二、公平对照要求

旧M3A日志出现过6次现金目标过期，不能直接作为M3E的唯一对照。必须用同一份`step04_joinquant_momentum_baseline.py` v0.9分别运行：

1. `RUN_MODE = "m3_ols_slope"`，得到`m3_ols_slope_engine_v0.9`；
2. `RUN_MODE = "m3e_huber_slope"`，得到`m3e_huber_slope_engine_v0.9`。

两次运行都使用2015-01-01至2020-12-31、100,000元、分钟频率。除模式外不能修改任何代码或平台设置。

## 三、必须报告

- 每月OLS与Huber的Top1、分数和选择分歧；
- Huber迭代次数及被降权价格点数量；
- 成熟选择标签数、精确率、无条件成功率、平均净收益；
- 年化收益、最大回撤、Calmar、Sharpe、Sortino、换手和成本；
- 删除最后一个价格点后Top1是否改变；
- Huber改善是否集中于单一ETF、年份或异常月份。

## 四、Huber强于OLS的判定

M3E首先必须通过步骤04绝对门槛：成熟选择标签不少于36、精确率不低于55%、比无条件成功率高至少5个百分点、平均净收益为正、年化不低于6.22%、最大回撤不高于34.96%、Calmar不低于0.4。

随后必须同时满足以下相对门槛：

- Huber选择精确率比当前引擎OLS至少提高5个百分点；
- Huber选择后的21日平均净收益不低于OLS；
- Huber Calmar不低于OLS；
- Huber年化收益相对OLS下降不超过1个百分点；
- Huber最大回撤相对OLS恶化不超过2个百分点；
- Huber必须实际改变至少一个月的选择，且改善不能只来自单一交易。

任一条件失败，不能宣称Huber强于OLS。

## 五、首次Huber结果

聚宽设置与版本正确：2015-01-01至2020-12-31、100,000元、分钟频率，日志首行为`m3e_huber_slope_engine_v0.9`。

| 指标 | M3E Huber | 绝对门槛 | 状态 |
|---|---:|---:|---|
| 累计收益 | 64.63% | 仅记录 | - |
| 年化收益 | 8.90% | 不低于6.22% | 通过 |
| 最大回撤 | 21.13% | 不高于34.96% | 通过 |
| Calmar | 约0.421 | 不低于0.4 | 通过 |
| Sharpe | 0.349 | 仅记录 | - |
| Sortino | 0.408 | 仅记录 | - |
| 策略波动率 | 14.0% | 仅记录 | - |
| Alpha | 0.042 | 仅记录 | - |
| Beta | 0.257 | 仅记录 | - |

相对旧M3A，累计收益提高3.15个百分点、年化提高0.36个百分点、最大回撤相同、Sharpe提高0.032、Sortino提高0.041、Calmar约提高0.017。但旧M3A不是同引擎v0.9公平对照，这些差异只能视为改善迹象。

附件日志共399行，只到2016-03-01。最后一条汇总为2016-02-01的`all=42`、`selected=8`、`selected_precision=25%`、`selected_avg_net=3.9567%`，不足以代表六年结果。2016-01-04买入511010时1100份委托成交717份，次日继续成交300份，剩余83份不足一手后正确结束；账户恒等式误差为0，没有执行故障。

因此当前不能宣称Huber强于OLS：最终成熟标签、55%精确率门槛、同引擎OLS相对门槛均未得到验证。

## 六、实现证据

- 聚宽脚本：`D:/Quant/step04_joinquant_momentum_baseline.py`；
- 本地参考：`D:/Quant/scripts/step04_momentum_logic.py`；
- 单元测试：`D:/Quant/tests/test_step04_momentum_logic.py`。

## 七、版本记录

| 版本 | 日期 | 变更内容 |
|---|---|---|
| v0.1-preregistered | 2026-07-13 | 冻结Huber IRLS参数、拟合质量口径和相对OLS判定门槛 |
| v0.2-preregistered | 2026-07-13 | 运行前数值复核：MAD达到数值下限时保留最后一组有效IRLS权重，不改变冻结参数 |
| v0.3-result1 | 2026-07-13 | 记录Huber组合绩效、正确的部分成交重试和标签证据缺口 |

## 八、最终决定

- 当前决定：不支持“已经证明Huber强于OLS”；用户另行授权M3F探索性运行；
- 允许进入步骤05：否；
- M3E剩余决策点：取得最终标签并完成v0.9 OLS成对审计。
