# =============================================================================
# ETF 跨资产配置 三原型 PK —— 聚宽 JoinQuant 回测版 (v2 性能优化)
# =============================================================================
# v2 变更(修"正在加载日志"卡死)：
#   · 数据层重写为【一次批量取全池 get_price】+ 当日缓存，不再逐腿逐日单独取价。
#     get_price 调用次数从上万次 -> 几十次，日频回测不再卡死。
#   · 其余逻辑/开关/口径与 v1 完全一致。
#
# 三原型：
#   M1   : 全池等权 + 月度再平衡，无择时
#   M2   : 全池风险平价(逆波动率) + 月度再平衡，无择时
#   M2M3 : M2 + 200日线危机滤网(单腿跌破切避险，站回月度调仓日买回)
#
# 用法：改 STRATEGY 一个字符串，各上传回测一次。
#   诊断卡死：先跑 STRATEGY='M1'(无日频循环)，若秒出=日频拖慢已被本版修复。
#   危机检测频率(仅 M2M3)：CHECK_DAILY  True=日频砍/月度买回  False=月频
#
# 池子(6腿,四象限)：512890红利低波 159915创业板 513100纳指 518880黄金
#                    159985豆粕 511260十年国债
# 核对：513100为QDII,取不到自动剔除+打日志(不崩)；起始>=2019-12-05；初始资金按真实体量设。
# 平台：聚宽 JoinQuant  |  调仓：月频  |  标的：ETF/LOF
# =============================================================================

import numpy as np
import pandas as pd
from jqdata import *

# ==================== 配置区（改这里） ====================
STRATEGY = 'M2M3'          # 'M1' | 'M2' | 'M2M3'
CHECK_DAILY = True         # 仅 M2M3 生效：True=日频检测，False=月频

POOL = [
    '512890.XSHG',  # 红利低波ETF
    '159915.XSHE',  # 创业板ETF
    '513100.XSHG',  # 纳指ETF (QDII，注意核对数据可用性)
    '518880.XSHG',  # 黄金ETF
    '159985.XSHE',  # 豆粕ETF
    '511260.XSHG',  # 十年国债ETF
]
SAFE_ASSET = '511260.XSHG'  # 危机滤网的避险目的地

MA_WINDOW = 200             # 危机滤网：长期均线窗口
VOL_WINDOW = 60             # 风险平价：波动率窗口
MIN_HISTORY = MA_WINDOW + 5


# ==================== 初始化 ====================
def initialize(context):
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_benchmark('510300.XSHG')
    set_slippage(PriceRelatedSlippage(0.0005), type='fund')
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0,
                  open_commission=0.0001, close_commission=0.0001,
                  close_today_commission=0, min_commission=5),
        type='fund')

    log.set_level('order', 'error')
    log.set_level('system', 'error')

    g.strategy = STRATEGY
    g.check_daily = CHECK_DAILY and (STRATEGY == 'M2M3')
    g.price_cache = {'date': None, 'data': None}   # 当日全池收盘价缓存

    log.info('========== 原型 %s | 危机日频检测=%s =========='
             % (g.strategy, g.check_daily))

    run_monthly(rebalance, 1, '10:00')
    if g.check_daily:
        run_daily(daily_crisis_check, '14:30')


# ==================== 数据层：一次批量取全池 + 当日缓存 ====================
def _pool_closes(context):
    """返回 dict: code -> 后复权收盘价 Series。整池一次 get_price，当日缓存复用。"""
    today = context.current_dt.date()
    if g.price_cache['date'] == today and g.price_cache['data'] is not None:
        return g.price_cache['data']

    end = context.previous_date
    data = {}
    try:
        df = get_price(POOL, count=MIN_HISTORY, end_date=end,
                       frequency='daily', fields=['close'],
                       fq='post', panel=False)
    except Exception as e:
        log.warn('批量取价失败: %s' % e)
        df = None

    if df is not None and len(df) > 0:
        # panel=False 多标的为长表(含 time/code/close)，pivot 成 code->Series
        try:
            wide = df.pivot(index='time', columns='code', values='close')
            for code in POOL:
                if code in wide.columns:
                    s = wide[code].dropna()
                    if len(s) > 0:
                        data[code] = s
        except Exception as e:
            log.warn('pivot失败: %s' % e)

    # 未取到的腿打日志(QDII等)
    for code in POOL:
        if code not in data:
            log.info('剔除 %s：数据不可用/历史不足' % code)

    g.price_cache = {'date': today, 'data': data}
    return data


def _available_legs(closes):
    return [c for c in POOL if c in closes and len(closes[c]) >= MA_WINDOW]


# ==================== 权重计算 ====================
def _base_weights(legs, closes):
    if g.strategy == 'M1':
        return {c: 1.0 / len(legs) for c in legs}
    # M2/M2M3：逆波动率
    inv = {}
    for c in legs:
        s = closes[c]
        if len(s) < VOL_WINDOW + 1:
            inv[c] = 0.0
            continue
        rets = s.iloc[-(VOL_WINDOW + 1):].pct_change().dropna()
        vol = rets.std()
        inv[c] = (1.0 / vol) if (vol and not np.isnan(vol) and vol > 0) else 0.0
    # 注意：from jqdata import * 会覆盖内置 sum，这里用 np.nansum 显式求和
    tot = float(np.nansum(list(inv.values())))
    if tot <= 0:
        return {c: 1.0 / len(legs) for c in legs}
    return {c: inv[c] / tot for c in legs}


def _apply_crisis_filter(legs, closes, base_w):
    """逐腿判断200日线，跌破份额转避险；避险腿自身跌破则留现金。"""
    target = {}
    defense_share = 0.0
    for c in legs:
        w = base_w.get(c, 0.0)
        s = closes[c]
        ma = s.iloc[-MA_WINDOW:].mean()
        price_now = s.iloc[-1]
        if price_now > ma:
            target[c] = target.get(c, 0.0) + w
        else:
            defense_share += w
            log.info('%s 跌破%d日线(%.4f<=%.4f)，%.1f%%转避险'
                     % (c, MA_WINDOW, price_now, ma, w * 100))

    if defense_share > 0:
        safe_ok = True
        if SAFE_ASSET in closes and len(closes[SAFE_ASSET]) >= MA_WINDOW:
            s = closes[SAFE_ASSET]
            safe_ok = s.iloc[-1] > s.iloc[-MA_WINDOW:].mean()
        if safe_ok:
            target[SAFE_ASSET] = target.get(SAFE_ASSET, 0.0) + defense_share
        else:
            log.info('避险腿%s亦跌破均线，%.1f%%留现金'
                     % (SAFE_ASSET, defense_share * 100))
    return target


# ==================== 月度再平衡 ====================
def rebalance(context):
    closes = _pool_closes(context)
    legs = _available_legs(closes)
    if not legs:
        log.warn('无可用腿，跳过调仓')
        return

    base_w = _base_weights(legs, closes)
    target = _apply_crisis_filter(legs, closes, base_w) if g.strategy == 'M2M3' else base_w

    _order_to_target(context, target)
    log.info('[%s] 目标权重：%s'
             % (g.strategy, {k: round(v, 3) for k, v in target.items()}))


def _order_to_target(context, target):
    total_value = context.portfolio.total_value
    for sec in list(context.portfolio.positions.keys()):
        if sec not in target:
            order_target_value(sec, 0)
    for sec, w in target.items():
        order_target_value(sec, total_value * w if w > 0 else 0)


# ==================== 日频危机检测（M2M3 + CHECK_DAILY） ====================
def daily_crisis_check(context):
    closes = _pool_closes(context)
    for sec in list(context.portfolio.positions.keys()):
        if sec == SAFE_ASSET:
            continue
        pos = context.portfolio.positions[sec]
        if pos.total_amount <= 0:
            continue
        if sec not in closes or len(closes[sec]) < MA_WINDOW:
            continue
        s = closes[sec]
        if s.iloc[-1] <= s.iloc[-MA_WINDOW:].mean():
            order_target_value(sec, 0)
            log.info('[日频砍仓] %s 跌破%d日线，清仓切现金(等月度买回)'
                     % (sec, MA_WINDOW))
