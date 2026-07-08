# -*- coding: utf-8 -*-
"""
红利低波(512890)乖离率 高抛低吸(均值回归)回测
====================================================
核心逻辑(先看这段,别只看代码):
  1) 乖离率 bias = (现价 - N日均线) / N日均线。
     价格跌破均线越多(bias 越负)= 超跌 -> 越便宜 -> 仓位越重;
     价格涨超均线越多(bias 越正)= 超涨 -> 越贵   -> 仓位越轻/清空。
     这是均值回归,契合红利低波的弱趋势+强震荡特性。
  2) 分档建仓/减仓,总仓位不超 MAX_POSITION。
  3) 年线(250日)风控:价格跌破年线时,强制把仓位上限压到 DEFENSIVE_CAP,
     不在下跌趋势里抄底半山腰(均值回归最大的死法)。站回年线再放开。
  4) 只交易 512890 这一只 ETF,换手低,契合控回撤+慢速复利。

关键防坑(都已在代码里处理):
  - 乖离率在【后复权 fq='post'】连续价格序列上算:ETF 除权当天价格向下跳空,
    用不复权价会被误判成"暴跌->负乖离爆表->触发买入",信号全乱。后复权序列
    连续,跳空消失,乖离率(比值)才干净。这就是"避开除权陷阱"。
  - 信号只用【截至上一交易日】的价格算,盘中不取当天(avoid_future_data 会拦)。
  - 交易成本按 ETF 实计:无印花税,佣金万1、单笔最低5元,双边滑点。
  - 换手率用 record 逐笔累计,回测结束打印;样本内/外用 IS_OOS_SPLIT 日期分段标注。

免责:乖离率阈值/均线窗口都是可过拟合的参数。务必分段看样本外(见 IS_OOS_SPLIT),
      别拿样本内调出来的漂亮曲线当常态。红利低波近年资金抱团,摆动变弱,更要警惕。
"""

import numpy as np
import pandas as pd
from jqdata import *


# ============================ 可调参数 ============================
ETF_CODE     = '512890.XSHG'   # 中证红利低波ETF(实际交易标的)

MA_WINDOW    = 60              # 乖离率基准均线窗口(交易日),60≈季度级
YEAR_MA      = 250            # 年线窗口(交易日),风控止损用

# 乖离率 -> 目标仓位(高抛低吸:bias 越负越便宜,仓位越重)
# 每档 (bias 下界, 目标仓位);从最便宜(最负)到最贵匹配
BIAS_BANDS = [
    (-0.12, 1.00),   # 跌破均线 12% 以上 -> 满仓
    (-0.08, 0.80),   # 跌 8%~12%        -> 80%
    (-0.04, 0.60),   # 跌 4%~8%         -> 60%
    ( 0.04, 0.40),   # 均线 ±4% 之间     -> 40% 基础仓
    ( 0.08, 0.20),   # 涨 4%~8%         -> 20%
    ( 1e9,  0.00),   # 涨 8% 以上        -> 清空
]

MAX_POSITION   = 1.00          # 总仓位上限
DEFENSIVE_CAP  = 0.20          # 跌破年线时的仓位上限(风控止损)
YEAR_MA_BUFFER = 0.00          # 年线缓冲:跌破 YEAR_MA*(1-buffer) 才触发,防毛刺
REBALANCE_TOL  = 0.05          # 目标与现仓偏离超此阈值才调仓,降换手

IS_OOS_SPLIT   = '2021-01-01'  # 样本内/外分界:此日期前为样本内(IS),之后为样本外(OOS)


def initialize(context):
    set_benchmark(ETF_CODE)
    set_option('use_real_price', True)      # 交易用真实价
    set_option('avoid_future_data', True)   # 拦未来数据,叠加代码层"用昨日"过滤
    set_order_cost(OrderCost(
        open_commission=0.0001, close_commission=0.0001,
        min_commission=5), type='fund')     # ETF 免印花,佣金万1、最低5元
    set_slippage(FixedSlippage(0.002))

    # 换手统计:累计成交额,用于估算换手率
    g.cum_turnover_value = 0.0
    g.last_regime = None

    # 每个交易日盘中判断(带调仓容差,不会天天真交易)
    run_daily(handle_rebalance, time='14:30')
    # 回测收尾打印换手率汇总
    run_daily(_daily_track, time='15:00')


def _post_adjusted_closes(context, n):
    """取截至上一交易日、长度 n 的【后复权】收盘价序列。
    后复权避开除权跳空,信号只用昨日及以前 -> 无未来函数。"""
    prev_day = context.previous_date
    df = get_price(ETF_CODE, end_date=prev_day, count=n,
                   frequency='daily', fields=['close'],
                   fq='post', panel=False)
    if df is None or len(df) < n:
        return None
    return df['close'].astype(float).values


def _target_weight_by_bias(bias):
    """按乖离率分档给目标仓位。"""
    for upper, w in BIAS_BANDS:
        if bias <= upper:
            return w
    return 0.0


def handle_rebalance(context):
    # 需要足够长的历史算年线
    closes = _post_adjusted_closes(context, YEAR_MA + 1)
    if closes is None:
        # 年线数据不足时,退而用 MA_WINDOW 起步(warmup 阶段仅按乖离,不做年线风控)
        closes = _post_adjusted_closes(context, MA_WINDOW + 1)
        if closes is None:
            log.info('价格历史不足,跳过')
            return
        year_ma = None
    else:
        year_ma = float(np.mean(closes[-YEAR_MA:]))

    ma = float(np.mean(closes[-MA_WINDOW:]))
    last_close = float(closes[-1])   # 上一交易日后复权收盘
    if ma <= 0:
        return
    bias = (last_close - ma) / ma

    target_w = _target_weight_by_bias(bias)
    target_w = min(target_w, MAX_POSITION)

    # 年线风控:跌破年线 -> 压到防御仓位上限(不抄底半山腰)
    below_year = False
    if year_ma is not None and last_close < year_ma * (1.0 - YEAR_MA_BUFFER):
        below_year = True
        target_w = min(target_w, DEFENSIVE_CAP)

    regime = 'BELOW_YEAR' if below_year else 'NORMAL'
    if regime != g.last_regime:
        log.info('风控状态切换: %s (last_close=%.4f, year_ma=%s)' %
                 (regime, last_close,
                  ('%.4f' % year_ma) if year_ma is not None else 'NA'))
        g.last_regime = regime

    # 样本内/外标注
    seg = 'IS' if str(context.current_dt.date()) < IS_OOS_SPLIT else 'OOS'

    total_value = context.portfolio.total_value
    pos = context.portfolio.positions.get(ETF_CODE)
    cur_value = pos.value if pos is not None else 0.0
    cur_w = cur_value / total_value if total_value > 0 else 0.0

    if abs(target_w - cur_w) < REBALANCE_TOL:
        return   # 偏离过小,不动,省换手

    # 记录本次调仓的成交额(用于换手率估算)
    trade_value = abs(target_w - cur_w) * total_value
    g.cum_turnover_value += trade_value

    log.info('[%s] bias=%.2f%% MA%d=%.4f 目标仓=%.0f%% 现仓=%.0f%% %s' %
             (seg, bias * 100, MA_WINDOW, ma,
              target_w * 100, cur_w * 100,
              '(年线风控)' if below_year else ''))

    order_target_value(ETF_CODE, total_value * target_w)


def _daily_track(context):
    """每日记录换手率(累计成交额/当前总资产,粗略双边口径)。"""
    tv = context.portfolio.total_value
    if tv > 0:
        record(累计换手倍数=g.cum_turnover_value / tv)
