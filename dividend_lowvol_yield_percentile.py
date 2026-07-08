# -*- coding: utf-8 -*-
"""
红利低波(512890 / 中证红利低波100 = 930955.XSHG)股息率分位 高抛低吸 回测
=======================================================================
核心逻辑(先看这段,别只看代码):
  1) 每月底,对指数100只成分股各算 "滚动12个月每股税前派息 / 现价 = 个股股息率"。
  2) 取成分股股息率的【中位数】作为指数股息率代理 DY_t(中位数抗个别异常派息)。
  3) 把 DY_t 放进【历史滚动窗口】算分位 —— 只用当天之前累积的数据,walk-forward,
     无未来函数。前 WARMUP_MONTHS 个月只累积不交易。
  4) 股息率分位越高 = 指数越便宜 -> 仓位越重(高抛低吸 / 均值回归):
        >=80% -> 100% ; 60~80% -> 75% ; 40~60% -> 50% ; 20~40% -> 25% ; <20% -> 0%
  5) 只交易 512890 这一只 ETF,不碰成分股,换手低。

关键防坑(都已在代码里处理):
  - 分红只取 plan_progress=='实施方案' 且 a_xr_date 已发生、board_plan_pub_date<=当日,
    杜绝用未公布/未实施的分红 -> 无未来函数。
  - bonus_ratio_rmb 是 "每10股派X元(税前)",所以每股派息 = bonus_ratio_rmb / 10。
  - 分位是 walk-forward 滚动窗口,不是全样本 -> 不偷看未来。
  - 交易成本按 ETF 实计:无印花税,佣金万1、单笔最低5元,滑点双边。

免责:历史股息率分位在 2016-2021 是甜蜜区,近年资金抱团后摆动变弱。务必分段看样本外,
      别把某一段的曲线当常态。参数(分位阈值/窗口)自己在样本外验证,别过拟合。
"""

import numpy as np
import pandas as pd
import datetime as dt
# 聚宽回测环境:finance / query / get_index_stocks 等都由这一行统一注入。
# 不要写 from jqdata import query(单独导入在回测环境会报错)。
from jqdata import *


# ============================ 可调参数 ============================
# 指数成分股来源:聚宽 get_index_stocks 不收录中证【策略指数】(如红利低波100=930955),
# 故给一条候选链,运行时自动探测第一个可用的,并在日志打出实际使用的指数。
# 顺序:红利低波100 -> 中证红利低波 -> 中证红利(宽基,聚宽基本必然支持,兜底)。
INDEX_CANDIDATES = ['930955.XSHG', 'H30269.XSHG', '000922.XSHG']
ETF_CODE     = '512890.XSHG'   # 实际交易的 ETF
WARMUP_MONTHS = 12             # 前 N 个月只累积股息率历史,不交易
PCTL_WINDOW   = 36             # 分位滚动窗口(月),36=近3年;设为 0 表示用全部历史(扩张窗口)
TTM_DAYS      = 365            # 滚动股息窗口(自然日)
# 分位 -> 目标仓位(高抛低吸:股息率分位越高越便宜,仓位越重)
PCTL_BANDS = [
    (0.80, 1.00),
    (0.60, 0.75),
    (0.40, 0.50),
    (0.20, 0.25),
    (0.00, 0.00),
]
REBALANCE_TOL = 0.05           # 目标仓位与现仓偏离超过该阈值才调仓,降换手


def initialize(context):
    set_benchmark(ETF_CODE)
    set_option('use_real_price', True)      # 用真实(后复权)价,红利策略必须,避免除权跳空误判
    set_option('avoid_future_data', True)
    # ETF 交易成本:无印花税,佣金万1、最低5元,双边滑点
    set_order_cost(OrderCost(
        open_commission=0.0001, close_commission=0.0001,
        min_commission=5), type='fund')
    set_slippage(FixedSlippage(0.002))

    g.dy_history = []          # walk-forward 股息率历史 [(date, dy), ...]
    g.month_count = 0
    g.used_index = None        # 探测确定后缓存实际使用的成分股指数代码

    # 每月底最后一个交易日盘中运行
    run_monthly(handle_rebalance, -1, time='14:30')


def _per_share_ttm_dividend(context, stock):
    """计算单只股票滚动 TTM 每股税前派息,只用已实施、已除权、已公告的分红(无未来函数)。"""
    today = context.current_dt.date()
    start = today - dt.timedelta(days=TTM_DAYS)
    try:
        df = finance.run_query(
            query(finance.STK_XR_XD.bonus_ratio_rmb,
                  finance.STK_XR_XD.a_xr_date,
                  finance.STK_XR_XD.board_plan_pub_date,
                  finance.STK_XR_XD.plan_progress)
            .filter(finance.STK_XR_XD.code == stock,
                    finance.STK_XR_XD.a_xr_date <= today,
                    finance.STK_XR_XD.a_xr_date > start)
        )
    except Exception:
        return 0.0
    if df is None or len(df) == 0:
        return 0.0

    total = 0.0
    for _, row in df.iterrows():
        # 只认已实施的分红
        prog = row.get('plan_progress')
        if prog is not None and ('实施' not in str(prog)):
            continue
        # 公告日必须已发生(双保险,防未来函数)
        pub = row.get('board_plan_pub_date')
        if pub is not None and not pd.isnull(pub):
            try:
                if pd.to_datetime(pub).date() > today:
                    continue
            except Exception:
                pass
        ratio = row.get('bonus_ratio_rmb')          # 每10股派X元(税前)
        if ratio is None or pd.isnull(ratio):
            continue
        total += float(ratio) / 10.0                # -> 每股派息
    return total


def _resolve_index_stocks(context):
    """按候选链探测第一个 get_index_stocks 能返回成分的指数。
    聚宽不收录中证策略指数(930955 等)时自动降级,并把实际使用的指数缓存+打日志。"""
    d = context.current_dt.date()
    # 已确定过用哪条指数,直接复用(避免每月重复试错 + 重复刷日志)
    used = getattr(g, 'used_index', None)
    if used is not None:
        try:
            s = get_index_stocks(used, date=d)
            if s:
                return s
        except Exception:
            pass  # 之前可用的这次取不到,重新走一遍候选链
    for code in INDEX_CANDIDATES:
        try:
            s = get_index_stocks(code, date=d)
        except Exception:
            continue
        if s:
            if getattr(g, 'used_index', None) != code:
                g.used_index = code
                log.info('成分股指数已选定: %s (成分数=%d)' % (code, len(s)))
            return s
    return None


def _index_dividend_yield(context):
    """指数股息率代理 = 成分股个股股息率的中位数(中位数抗异常派息)。"""
    stocks = _resolve_index_stocks(context)
    if not stocks:
        return None
    # avoid_future_data=True 时盘中取不到"当天"日线收盘(当天未收盘=未来数据),
    # 用上一交易日收盘价算股息率:月底调仓用昨日确定收盘价,信息无损、无未来函数。
    prev_day = context.previous_date
    prices = get_price(stocks, end_date=prev_day, count=1,
                       fields=['close'], panel=False)
    if prices is None or len(prices) == 0:
        return None
    last_close = prices.groupby('code')['close'].last()

    yields = []
    for s in stocks:
        px = last_close.get(s)
        if px is None or pd.isnull(px) or px <= 0:
            continue
        dps = _per_share_ttm_dividend(context, s)
        if dps <= 0:
            continue
        yields.append(dps / float(px))
    if len(yields) < 10:        # 有效样本太少,信号不可信
        return None
    return float(np.median(yields))


def _percentile_of_last(values):
    """当前值(列表最后一个)在历史序列中的分位(0~1),walk-forward。"""
    if len(values) < 2:
        return None
    arr = np.asarray(values[:-1], dtype=float)   # 用"之前"的历史,不含当前
    cur = float(values[-1])
    return float((arr <= cur).sum()) / float(len(arr))


def _target_weight(pctl):
    for thr, w in PCTL_BANDS:
        if pctl >= thr:
            return w
    return 0.0


def handle_rebalance(context):
    g.month_count += 1
    dy = _index_dividend_yield(context)
    if dy is None:
        log.info('股息率无法计算,跳过本月')
        return

    g.dy_history.append((context.current_dt.date(), dy))

    # 滚动窗口裁剪
    if PCTL_WINDOW and len(g.dy_history) > PCTL_WINDOW:
        g.dy_history = g.dy_history[-PCTL_WINDOW:]

    # warmup:只累积不交易
    if g.month_count <= WARMUP_MONTHS:
        log.info('warmup %d/%d, DY=%.4f, 暂不交易' %
                 (g.month_count, WARMUP_MONTHS, dy))
        return

    vals = [x[1] for x in g.dy_history]
    pctl = _percentile_of_last(vals)
    if pctl is None:
        return

    target_w = _target_weight(pctl)

    # 现仓位
    total_value = context.portfolio.total_value
    pos = context.portfolio.positions.get(ETF_CODE)
    cur_value = pos.value if pos is not None else 0.0
    cur_w = cur_value / total_value if total_value > 0 else 0.0

    log.info('DY=%.4f 分位=%.1f%% 目标仓=%.0f%% 现仓=%.0f%%' %
             (dy, pctl * 100, target_w * 100, cur_w * 100))

    if abs(target_w - cur_w) < REBALANCE_TOL:
        return   # 偏离过小,不动,省换手

    order_target_value(ETF_CODE, total_value * target_w)
