# -*- coding: utf-8 -*-
"""
红利低波(512890)网格 高抛低吸(震荡收割 + 战略底仓)回测
==========================================================
说明:本策略基于【网格交易通用方法论】+ 针对红利低波标的的改进设计。
     并非复述某篇具体文章(原文未能获取);"红利网格"思路是公开成熟打法。

核心逻辑(先看这段,别只看代码):
  1) 网格 = 围绕"中枢价"分层高抛低吸:价格每跌一格 -> 加一份机动仓,
     每涨一格 -> 减一份机动仓。赚的是震荡的波动差,不赌方向。
  2) 中枢价 = 滚动均线(MA_CENTER),不用固定锚 —— 慢牛里中枢会上移,
     固定锚的网格会整体失效/被套。用均线让网格跟着中枢漂。
  3) 【战略底仓 BASE_POS 常驻】(默认 50%),吃趋势+股息,解决纯网格
     在慢牛里踏空、现金拖累的病根。网格只在 [BASE_POS, MAX_POSITION]
     区间内用【机动仓】做增强。
  4) 总仓位 = 底仓 + 机动仓(由价格相对中枢的偏离档位决定)。
  5) 只交易 512890 这一只 ETF。

关键防坑(都已在代码里处理):
  - 网格线/偏离在【后复权 fq='post'】价格上算:除权当天价格向下跳空,
    不复权会被误判成"暴跌->触发买入",网格全乱。后复权序列连续,干净。
  - 信号只用【截至上一交易日】价格,盘中不取当天(avoid_future_data 会拦)。
  - 年线(YEAR_MA)风控:跌破年线 -> 机动仓上限压到 0,只留底仓,不接飞刀。
  - 交易成本按 ETF 实计:无印花税,佣金万1、单笔最低5元,双边滑点。
  - REBALANCE_TOL 容差,偏离过小不动,压低网格换手(否则万1+5元起会被磨死)。
  - 换手率用 record 逐笔累计;样本内/外用 IS_OOS_SPLIT 日期分段标注。

免责:网格间距/档数/底仓比例都是可过拟合参数。务必看 IS_OOS_SPLIT 前后两段,
      别拿样本内调出的漂亮曲线当常态。网格只在震荡市有效,单边市会跑输底仓。
"""

import numpy as np
import pandas as pd
from jqdata import *


# ============================ 可调参数 ============================
ETF_CODE     = '512890.XSHG'   # 中证红利低波ETF

MA_CENTER    = 60              # 网格中枢均线窗口(交易日),60≈季度中枢
YEAR_MA      = 250             # 年线窗口,风控用

BASE_POS     = 0.50            # 战略底仓(常驻,吃趋势+股息)
MAX_POSITION = 1.00            # 总仓位上限

# 网格:价格相对中枢的偏离 -> 机动仓位(叠加在底仓之上)
# 偏离越负(越跌)机动仓越重;偏离为正(涨)机动仓归零甚至只留底仓。
# (偏离上界, 机动仓位)。机动仓最终会被 clip 到 [0, MAX_POSITION-BASE_POS]。
GRID_BANDS = [
    (-0.10, 0.50),   # 跌破中枢 10% 以上 -> 机动仓拉满(总仓 = 底仓+0.50)
    (-0.06, 0.40),   # 跌 6%~10%
    (-0.03, 0.25),   # 跌 3%~6%
    ( 0.00, 0.15),   # 中枢下方 0~3%
    ( 0.03, 0.05),   # 中枢上方 0~3%
    ( 0.06, 0.00),   # 涨 3%~6% -> 机动清零,只留底仓
    ( 1e9,  0.00),   # 涨 6% 以上 -> 只留底仓(高抛)
]

YEAR_MA_BUFFER = 0.00          # 年线缓冲:跌破 YEAR_MA*(1-buffer) 触发风控
REBALANCE_TOL  = 0.04          # 目标与现仓偏离超此阈值才调仓,降换手
IS_OOS_SPLIT   = '2021-01-01'  # 样本内/外分界


def initialize(context):
    set_benchmark(ETF_CODE)
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_order_cost(OrderCost(
        open_commission=0.0001, close_commission=0.0001,
        min_commission=5), type='fund')     # ETF 免印花,佣金万1、最低5元
    set_slippage(FixedSlippage(0.002))

    g.cum_turnover_value = 0.0
    g.last_regime = None

    run_daily(handle_rebalance, time='14:30')
    run_daily(_daily_track, time='15:00')


def _post_adjusted_closes(context, n):
    """取截至上一交易日、长度 n 的后复权收盘价序列(无未来函数)。"""
    prev_day = context.previous_date
    df = get_price(ETF_CODE, end_date=prev_day, count=n,
                   frequency='daily', fields=['close'],
                   fq='post', panel=False)
    if df is None or len(df) < n:
        return None
    return df['close'].astype(float).values


def _grid_active_weight(deviation):
    """按价格相对中枢的偏离,给机动仓位。"""
    for upper, w in GRID_BANDS:
        if deviation <= upper:
            return w
    return 0.0


def handle_rebalance(context):
    # 取足够长历史算年线;不足则退到中枢均线起步(warmup 阶段无年线风控)
    closes = _post_adjusted_closes(context, YEAR_MA + 1)
    if closes is None:
        closes = _post_adjusted_closes(context, MA_CENTER + 1)
        if closes is None:
            log.info('价格历史不足,跳过')
            return
        year_ma = None
    else:
        year_ma = float(np.mean(closes[-YEAR_MA:]))

    center = float(np.mean(closes[-MA_CENTER:]))   # 网格中枢
    last_close = float(closes[-1])                 # 上一交易日后复权收盘
    if center <= 0:
        return
    deviation = (last_close - center) / center     # 相对中枢偏离

    # 机动仓(网格),clip 到 [0, MAX-BASE]
    active_w = _grid_active_weight(deviation)
    active_cap = max(0.0, MAX_POSITION - BASE_POS)
    active_w = min(active_w, active_cap)

    # 年线风控:跌破年线 -> 机动仓清零,只留底仓,不接飞刀
    below_year = False
    if year_ma is not None and last_close < year_ma * (1.0 - YEAR_MA_BUFFER):
        below_year = True
        active_w = 0.0

    target_w = min(BASE_POS + active_w, MAX_POSITION)

    regime = 'BELOW_YEAR' if below_year else 'NORMAL'
    if regime != g.last_regime:
        log.info('风控状态切换: %s (last_close=%.4f, year_ma=%s)' %
                 (regime, last_close,
                  ('%.4f' % year_ma) if year_ma is not None else 'NA'))
        g.last_regime = regime

    seg = 'IS' if str(context.current_dt.date()) < IS_OOS_SPLIT else 'OOS'

    total_value = context.portfolio.total_value
    pos = context.portfolio.positions.get(ETF_CODE)
    cur_value = pos.value if pos is not None else 0.0
    cur_w = cur_value / total_value if total_value > 0 else 0.0

    if abs(target_w - cur_w) < REBALANCE_TOL:
        return   # 偏离过小,不动,省换手

    trade_value = abs(target_w - cur_w) * total_value
    g.cum_turnover_value += trade_value

    log.info('[%s] dev=%.2f%% 中枢MA%d=%.4f 底仓=%.0f%% 机动=%.0f%% 目标=%.0f%% 现仓=%.0f%% %s' %
             (seg, deviation * 100, MA_CENTER, center,
              BASE_POS * 100, active_w * 100, target_w * 100, cur_w * 100,
              '(年线风控)' if below_year else ''))

    order_target_value(ETF_CODE, total_value * target_w)


def _daily_track(context):
    """每日记录累计换手倍数(累计成交额/当前总资产,粗略双边口径)。"""
    tv = context.portfolio.total_value
    if tv > 0:
        record(累计换手倍数=g.cum_turnover_value / tv)
