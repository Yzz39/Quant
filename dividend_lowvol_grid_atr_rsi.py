# -*- coding: utf-8 -*-
"""
红利低波(512890)网格·ATR自适应间距 + RSI择时过滤 + 战略底仓  回测
========================================================================
来源:融合一篇知乎"红利网格(ATR自适应+RSI择时)"文章的两点干货,
     + 上一版"底仓+滚动中枢+年线风控"框架。弃掉原文两个坑(见下)。

原文哪些抄了、哪些弃了(诚实标注):
  【抄】ATR 自适应网格间距:波动大->间距放宽,波动小->间距收窄。抗过拟合,
        比死间距强。原文用 0.5*ATR,这里做成可调 ATR_MULT。
  【抄】RSI 择时过滤:只在 RSI 超卖区才允许加仓、超买区才允许减仓,
        治网格"趋势里逆势操作"的病。
  【弃】固定基准价 1.344:典型的固定锚过拟合,慢牛里整个网格失效。
        改用滚动均线中枢(MA_CENTER),网格跟着中枢漂。
  【弃】纯网格无底仓:现金拖累+踏空趋势(用户上一轮"收益低"的病根)。
        保留 BASE_POS 战略底仓。
  【弃】倍数委托/反向撤单/tick状态码:那是 PTrade/QMT 实盘 tick 细节,
        日线回测无意义,不移植。

核心逻辑(先看这段,别只看代码):
  1) 中枢价 = MA_CENTER 日后复权均线;偏离 = (昨收 - 中枢)/中枢。
  2) 网格间距 = ATR_MULT * ATR/中枢(把ATR归一成百分比)。偏离每超过 k 个
     间距,机动仓加/减一档。波动自适应,不用手调死档位。
  3) RSI 过滤(可开关):加仓需 RSI<=RSI_BUY(超卖),减仓需 RSI>=RSI_SELL
     (超买)。RSI 处中性区时,机动仓维持不动(不逆势、不追高杀跌)。
  4) 总仓 = BASE_POS 底仓 + 机动仓([0, MAX-BASE])。跌破年线机动清零只留底仓。
  5) 只交易 512890 这一只 ETF。

关键防坑(都已处理):
  - 所有价格用【后复权 fq='post'】:除权跳空不污染网格/ATR/RSI。
  - 信号只用【截至上一交易日】的序列,盘中不取当天(avoid_future_data 会拦)。
  - 交易成本 ETF 实计:无印花税,佣金万1、单笔最低5元,双边滑点。
  - REBALANCE_TOL 容差,压低换手(万1+5元起,换手高会被磨死)。
  - 换手用 record 累计;IS/OOS 用 IS_OOS_SPLIT 分段标注。

⚠️ 重要提醒:原文 RSI 阈值 20/80 是【6分钟线】上的,日线极难触发。这里
   默认放宽到 30/70,且 USE_RSI_FILTER 可关。务必对比"开/关RSI"两种结果——
   若开了RSI后常年只拿底仓,说明日线上过滤太严,关掉或再放宽。

免责:ATR倍数/RSI阈值/底仓比例/档位都是可过拟合参数。务必看 IS_OOS_SPLIT
     前后两段。网格只在震荡市有效,单边大涨会跑输纯底仓(这是网格宿命,非bug)。
"""

import numpy as np
import pandas as pd
from jqdata import *


# ============================ 可调参数 ============================
ETF_CODE     = '512890.XSHG'   # 中证红利低波ETF

MA_CENTER    = 60              # 网格中枢均线窗口(交易日)
YEAR_MA      = 250             # 年线窗口,风控用

BASE_POS     = 0.50            # 战略底仓(常驻,吃趋势+股息)
MAX_POSITION = 1.00            # 总仓位上限

# --- ATR 自适应间距 ---
ATR_WINDOW   = 14              # ATR 窗口(交易日),原文用 ewm(com=14)
ATR_MULT     = 0.5             # 网格间距 = ATR_MULT * (ATR/中枢);原文 0.5,建议 0.3~0.8
ACTIVE_STEP  = 0.10            # 每档机动仓步长;偏离每超一个间距,机动仓变动一档

# --- RSI 择时过滤 ---
USE_RSI_FILTER = True          # 是否启用 RSI 过滤(先跑 True/False 各一次做对比)
RSI_WINDOW   = 14              # 日线 RSI 窗口(原文6分钟周期,日线用14更合理)
RSI_BUY      = 30.0            # RSI<=此值才允许加仓(超卖);原文20对日线太严
RSI_SELL     = 70.0            # RSI>=此值才允许减仓(超买);原文80对日线太严

YEAR_MA_BUFFER = 0.00          # 年线缓冲
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
    g.active_w = 0.0            # 当前机动仓(网格状态,跨日保持,RSI中性时不动)

    run_daily(handle_rebalance, time='14:30')
    run_daily(_daily_track, time='15:00')


def _post_ohlc(context, n):
    """取截至上一交易日、长度 n 的后复权 OHLC 序列(无未来函数)。"""
    prev_day = context.previous_date
    df = get_price(ETF_CODE, end_date=prev_day, count=n,
                   frequency='daily',
                   fields=['high', 'low', 'close'],
                   fq='post', panel=False)
    if df is None or len(df) < n:
        return None
    return df


def _atr_pct(df, center):
    """ATR 归一成相对中枢的百分比(和偏离同量纲)。原文 TR 三项取max + ewm。"""
    high = df['high'].astype(float).values
    low = df['low'].astype(float).values
    close = df['close'].astype(float).values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr1 = high - low
    tr2 = np.abs(high - prev_close)
    tr3 = np.abs(low - prev_close)
    tr = np.maximum.reduce([tr1, tr2, tr3])
    # ewm(com=ATR_WINDOW) 的等价:alpha = 1/(1+com)
    atr_series = pd.Series(tr).ewm(com=ATR_WINDOW).mean().values
    atr = float(atr_series[-1])
    if center <= 0:
        return None
    return atr / center


def _rsi(df, window):
    """经典 Wilder RSI(用后复权收盘,截至上一交易日)。"""
    close = df['close'].astype(float).values
    if len(close) < window + 1:
        return None
    diff = np.diff(close)
    gain = np.where(diff > 0, diff, 0.0)
    loss = np.where(diff < 0, -diff, 0.0)
    # Wilder 平滑
    avg_gain = np.mean(gain[:window])
    avg_loss = np.mean(loss[:window])
    for i in range(window, len(gain)):
        avg_gain = (avg_gain * (window - 1) + gain[i]) / window
        avg_loss = (avg_loss * (window - 1) + loss[i]) / window
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def handle_rebalance(context):
    need = max(YEAR_MA, MA_CENTER, ATR_WINDOW, RSI_WINDOW) + 2
    df = _post_ohlc(context, need)
    if df is None:
        # 历史不足,退到中枢+ATR 起步(warmup 无年线风控)
        df = _post_ohlc(context, max(MA_CENTER, ATR_WINDOW, RSI_WINDOW) + 2)
        if df is None:
            log.info('价格历史不足,跳过')
            return
        year_ma = None
    else:
        year_ma = float(np.mean(df['close'].astype(float).values[-YEAR_MA:]))

    closes = df['close'].astype(float).values
    center = float(np.mean(closes[-MA_CENTER:]))
    last_close = float(closes[-1])
    if center <= 0:
        return
    deviation = (last_close - center) / center

    # ATR 自适应间距(百分比量纲)
    grid = _atr_pct(df, center)
    if grid is None or grid <= 0:
        return
    grid = ATR_MULT * grid
    if grid <= 0:
        return

    # 目标机动档位:偏离是几个间距(负=跌=该加仓,正=涨=该减仓)
    n_grids = deviation / grid
    # 理论机动仓:跌越多越重。-n_grids 为正表示超跌
    raw_active = (-n_grids) * ACTIVE_STEP
    active_cap = max(0.0, MAX_POSITION - BASE_POS)
    target_active = min(max(raw_active, 0.0), active_cap)

    # RSI 择时过滤:只在超卖区才允许加仓、超买区才允许减仓,否则维持现状
    rsi = _rsi(df, RSI_WINDOW) if USE_RSI_FILTER else None
    if USE_RSI_FILTER and rsi is not None:
        if target_active > g.active_w:          # 想加仓
            if rsi <= RSI_BUY:
                g.active_w = target_active       # 确认超卖,允许加
            # 否则不加(不追,等超卖)
        elif target_active < g.active_w:         # 想减仓
            if rsi >= RSI_SELL:
                g.active_w = target_active       # 确认超买,允许减
            # 否则不减(不杀跌,等超买)
        # target==current 不动
    else:
        g.active_w = target_active               # 不启用RSI:纯ATR网格

    active_w = g.active_w

    # 年线风控:跌破年线 -> 机动清零,只留底仓
    below_year = False
    if year_ma is not None and last_close < year_ma * (1.0 - YEAR_MA_BUFFER):
        below_year = True
        active_w = 0.0
        g.active_w = 0.0

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
        return

    trade_value = abs(target_w - cur_w) * total_value
    g.cum_turnover_value += trade_value

    log.info('[%s] dev=%.2f%% 间距=%.2f%% RSI=%s 机动=%.0f%% 目标=%.0f%% 现仓=%.0f%% %s' %
             (seg, deviation * 100, grid * 100,
              ('%.0f' % rsi) if rsi is not None else 'OFF',
              active_w * 100, target_w * 100, cur_w * 100,
              '(年线风控)' if below_year else ''))

    order_target_value(ETF_CODE, total_value * target_w)


def _daily_track(context):
    """每日记录累计换手倍数(累计成交额/当前总资产,粗略双边口径)。"""
    tv = context.portfolio.total_value
    if tv > 0:
        record(累计换手倍数=g.cum_turnover_value / tv)
