# =============================================================================
# S4 + S3 组合 ETF 轮动策略 —— 聚宽 JoinQuant 回测骨架
# =============================================================================
# 来源：知乎"稳赚不赔"问题里剥离引流话术后，唯二可回测的因子雏形
#   S4 = 250日年线趋势开关（宴安#3）→ 大盘 regime 层，控回撤
#   S3 = 月线MACD定方向 + 日线20均线择时（YT笔记）→ 选腿层，抓趋势
#
# 三层结构（对齐用户既有 3-tier regime 框架）：
#   [大盘 regime]  沪深300指数 MA250:
#       进攻 = 收盘>MA250 且 MA250拐头向上(20日前更低)
#       震荡 = 收盘>MA250 但 MA250走平/向下
#       防御 = 收盘<MA250            → 切高股息防御篮子(不切现金)
#   [选腿 S3]  进攻/震荡 regime 下，行业ETF进攻池:
#       多头方向门: 月线 MACD  DIF>DEA (景气动量)
#       择时门:     日线 收盘>MA20
#       双过滤后按 LOOKBACK 动量排名取 top-N，逆波动率加权
#       不足 N 腿 → 缺口权重给防御(国债)，绝不凑弱腿追高
#   [快平仓 CLOSE信号]  日频检查:
#       持有进攻腿日线跌破 MA20 → 当日砍到国债避险(不等月度)
#       指数日线跌破 MA250     → 当日整体切防御
#
# 设计取向（对齐用户目标）：低回撤 > CAGR，抗过拟合，close信号优先于open。
# 平台：聚宽 JoinQuant | 调仓：月频+日频止损 | 标的：行业ETF/防御ETF
# =============================================================================

import datetime
import numpy as np
import pandas as pd
from jqdata import *

# ==================== 配置区（改这里） ====================
# --- 进攻候选：分两层「意图池」，实际入池由时点构池(PIT)动态决定 ---
# 行业层：申万一级行业代表ETF（景气动量轮动首选对象，多在2016年后上市）
SECTOR_CANDIDATES = [
    '512880.XSHG',  # 证券   (2016)
    '512800.XSHG',  # 银行   (2017)
    '512690.XSHG',  # 酒     (2019)
    '512010.XSHG',  # 医药   (2015)
    '512170.XSHG',  # 医疗   (2019)
    '512480.XSHG',  # 半导体 (2019)
    '515030.XSHG',  # 新能源车(2020)
    '515790.XSHG',  # 光伏   (2020)
    '512660.XSHG',  # 军工   (2016)
    '512400.XSHG',  # 有色   (2017)
    '512980.XSHG',  # 传媒   (2018)
    '515230.XSHG',  # 软件   (2021)
    '159928.XSHE',  # 消费   (2015)
]

# 宽基/风格/跨资产层：早年(行业ETF尚未成军)及行业腿不足时的降级对象。
# 这批多在2014年前后凑齐，能把有效回测区间往前推。
BROAD_CANDIDATES = [
    '510050.XSHG',  # 上证50   (2004)
    '510300.XSHG',  # 沪深300  (2012)
    '510500.XSHG',  # 中证500  (2013)
    '159915.XSHE',  # 创业板   (2011)
    '159901.XSHE',  # 深100    (2006)
    '518880.XSHG',  # 黄金     (2013)
    '513100.XSHG',  # 纳指     (2013, QDII)
]

# 防御篮子：高股息/低波（防御 regime 时持有，逆波动率加权）
DEFENSE_POOL = [
    '512890.XSHG',  # 红利低波
    '512800.XSHG',  # 银行（高股息）
    '511260.XSHG',  # 十年国债
]
SAFE_ASSET = '511260.XSHG'   # 日频砍仓/缺口权重的避险目的地
REGIME_INDEX = '000300.XSHG' # 大盘 regime 判定标的（沪深300指数）
BENCH = '510300.XSHG'        # 回测基准

# --- 时点构池(PIT)参数：消除幸存者偏差 + 防残缺信号裸奔 ---
MIN_LIST_DAYS = 400   # 上市满多少自然日才够入池（覆盖 MA250+LOOKBACK 的交易日历史）
MIN_SECTOR_LEGS = 5   # 行业腿够这么多才用纯行业层，否则降级并入宽基

# ---- 参数（全部明文阈值，可回测，非拍脑袋） ----
MA_REGIME = 250    # S4 年线窗口
REGIME_SLOPE_LAG = 20   # 年线拐头判定：MA250[t] vs MA250[t-20]
LOOKBACK = 120     # S3 动量回看窗口（日）
MA_TIMING = 20     # S3 日线择时/止损均线
VOL_WINDOW = 60    # 逆波动率窗口
TOP_N = 3          # 进攻腿最大持有数
MACD_FAST, MACD_SLOW, MACD_SIGNAL = 12, 26, 9

# ---- 开关 ----
STRICT_MACD = False        # True: 月线还要求 DIF>0（更严，切换更少）
ENABLE_DAILY_STOP = True   # 日频 MA20 止损（CLOSE信号，用户教条核心）
ENABLE_DAILY_REGIME = True # 日频年线破位 → 整体切防御
# 注：S3原文的 涨幅>30%减1/3、>50%减半 止盈，是针对个股高波动设计；
#     ETF波动低、且砍赢家伤动量，默认不启用，如需可自行加。

MIN_HISTORY = 300          # 日线最小历史（覆盖 MA250 + LOOKBACK）
MONTHLY_COUNT = 40         # 月线取样根数（覆盖 MACD26+9）


# ==================== 初始化 ====================
def initialize(context):
    set_option('avoid_future_data', True)
    set_option('use_real_price', True)
    set_benchmark(BENCH)
    set_slippage(PriceRelatedSlippage(0.0005), type='fund')
    # 用户实盘口径：佣金万1，单笔最低5元
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0,
                  open_commission=0.0001, close_commission=0.0001,
                  close_today_commission=0, min_commission=5),
        type='fund')

    log.set_level('order', 'error')
    log.set_level('system', 'error')

    g.daily_cache = {'date': None, 'data': None}   # 当日日线收盘缓存
    g.monthly_cache = {'month': None, 'data': None} # 当月月线收盘缓存
    g.attack_pool = list(ALL_ATTACK)   # 当前进攻池，rebalance 每月用 PIT 刷新

    log.info('====== S4+S3 组合 ETF 轮动 | topN=%d lookback=%d ma250=%d ======'
             % (TOP_N, LOOKBACK, MA_REGIME))

    run_monthly(rebalance, 1, '10:00')
    if ENABLE_DAILY_STOP or ENABLE_DAILY_REGIME:
        run_daily(daily_close_check, '14:30')


# 全部进攻候选（行业+宽基）——用于取价与"是否进攻腿"判定（不随PIT变化）
ALL_ATTACK = SECTOR_CANDIDATES + BROAD_CANDIDATES


# ==================== 时点构池 (PIT, 消除幸存者偏差) ====================
def _pit_universe(context):
    """当前调仓日真实可用的进攻池。
       规则：get_all_securities(date=当日) 取当时存在的证券 → 卡上市满
       MIN_LIST_DAYS → 行业腿够 MIN_SECTOR_LEGS 就纯行业，否则并入宽基降级。
       返回 code 列表；同时 log 出本月实际入池情况，便于一眼看穿空跑段。"""
    d = context.previous_date
    try:
        allsec = get_all_securities(types=['etf'], date=d)
        exist = set(allsec.index)
    except Exception as e:
        log.warn('get_all_securities 失败，回退全候选: %s' % e)
        exist = set(ALL_ATTACK)
        allsec = None

    cutoff = d - datetime.timedelta(days=MIN_LIST_DAYS)

    def _eligible(cands):
        out = []
        for c in cands:
            if c not in exist:
                continue
            if allsec is not None and c in allsec.index:
                sd = allsec.at[c, 'start_date']
                # start_date 为 date/Timestamp；上市不够老则剔除
                if pd.Timestamp(sd).date() > cutoff:
                    continue
            out.append(c)
        return out

    sectors = _eligible(SECTOR_CANDIDATES)
    if len(sectors) >= MIN_SECTOR_LEGS:
        pool = sectors
        tier = '行业'
    else:
        pool = sectors + _eligible(BROAD_CANDIDATES)
        tier = '宽基降级(行业仅%d腿)' % len(sectors)

    log.info('[PIT %s] 入池%d腿[%s]: %s'
             % (d, len(pool), tier, pool))
    return pool


# ==================== 数据层：批量取价 + 缓存 ====================
def _all_codes():
    codes = set(ALL_ATTACK) | set(DEFENSE_POOL) | {SAFE_ASSET}
    return list(codes)


def _daily_closes(context):
    """整池日线后复权收盘，dict: code -> Series。当日缓存复用。"""
    today = context.current_dt.date()
    if g.daily_cache['date'] == today and g.daily_cache['data'] is not None:
        return g.daily_cache['data']

    data = {}
    try:
        df = get_price(_all_codes(), count=MIN_HISTORY, end_date=context.previous_date,
                       frequency='daily', fields=['close'], fq='post', panel=False)
    except Exception as e:
        log.warn('批量取日线失败: %s' % e)
        df = None

    if df is not None and len(df) > 0:
        try:
            wide = df.pivot(index='time', columns='code', values='close')
            for c in wide.columns:
                s = wide[c].dropna()
                if len(s) > 0:
                    data[c] = s
        except Exception as e:
            log.warn('日线pivot失败: %s' % e)

    g.daily_cache = {'date': today, 'data': data}
    return data


def _monthly_closes(context):
    """进攻池月线后复权收盘，dict: code -> Series。当月缓存复用（月线更新慢）。"""
    ym = (context.current_dt.year, context.current_dt.month)
    if g.monthly_cache['month'] == ym and g.monthly_cache['data'] is not None:
        return g.monthly_cache['data']

    data = {}
    try:
        df = get_price(g.attack_pool, count=MONTHLY_COUNT, end_date=context.previous_date,
                       frequency='monthly', fields=['close'], fq='post', panel=False)
    except Exception as e:
        log.warn('批量取月线失败: %s' % e)
        df = None

    if df is not None and len(df) > 0:
        try:
            wide = df.pivot(index='time', columns='code', values='close')
            for c in wide.columns:
                s = wide[c].dropna()
                if len(s) > 0:
                    data[c] = s
        except Exception as e:
            log.warn('月线pivot失败: %s' % e)

    g.monthly_cache = {'month': ym, 'data': data}
    return data


def _index_closes(context):
    """大盘 regime 指数日线收盘 Series。"""
    try:
        df = get_price(REGIME_INDEX, count=MA_REGIME + REGIME_SLOPE_LAG + 5,
                       end_date=context.previous_date, frequency='daily',
                       fields=['close'], panel=False)
        if df is not None and len(df) > 0:
            return df['close'].dropna()
    except Exception as e:
        log.warn('取指数失败: %s' % e)
    return pd.Series(dtype=float)


# ==================== 指标 ====================
def _macd_bull(close, strict=False):
    """月线 MACD 是否多头：DIF>DEA（strict 时还要 DIF>0）。"""
    if len(close) < MACD_SLOW + MACD_SIGNAL:
        return False
    ema_f = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_s = close.ewm(span=MACD_SLOW, adjust=False).mean()
    dif = ema_f - ema_s
    dea = dif.ewm(span=MACD_SIGNAL, adjust=False).mean()
    bull = dif.iloc[-1] > dea.iloc[-1]
    if strict:
        bull = bull and (dif.iloc[-1] > 0)
    return bool(bull)


def _regime(idx_close):
    """S4 三档 regime：'attack' / 'range' / 'defense'。"""
    if len(idx_close) < MA_REGIME + REGIME_SLOPE_LAG:
        return 'range'  # 历史不足，保守走震荡（进攻但可缩腿）
    ma_now = idx_close.iloc[-MA_REGIME:].mean()
    ma_past = idx_close.iloc[-(MA_REGIME + REGIME_SLOPE_LAG):-REGIME_SLOPE_LAG].mean()
    price = idx_close.iloc[-1]
    if price < ma_now:
        return 'defense'
    return 'attack' if ma_now > ma_past else 'range'


def _inv_vol_weights(codes, closes):
    """逆波动率加权，权重和为1；异常回退等权。"""
    inv = {}
    for c in codes:
        s = closes.get(c)
        if s is None or len(s) < VOL_WINDOW + 1:
            inv[c] = 0.0
            continue
        rets = s.iloc[-(VOL_WINDOW + 1):].pct_change().dropna()
        vol = rets.std()
        inv[c] = (1.0 / vol) if (vol and not np.isnan(vol) and vol > 0) else 0.0
    tot = float(np.nansum(list(inv.values())))
    if tot <= 0:
        return {c: 1.0 / len(codes) for c in codes}
    return {c: inv[c] / tot for c in codes}


# ==================== 选腿 (S3) ====================
def _select_offense(context, closes, monthly):
    """双过滤后按动量取 top-N。返回 (选中腿list, 缺口数)。"""
    scored = []
    for c in g.attack_pool:
        s = closes.get(c)
        if s is None or len(s) < LOOKBACK + 1:
            continue
        # 门1：月线 MACD 多头（景气方向）
        m = monthly.get(c)
        if m is None or not _macd_bull(m, STRICT_MACD):
            continue
        # 门2：日线站上 MA20（择时）
        if s.iloc[-1] <= s.iloc[-MA_TIMING:].mean():
            continue
        # 动量打分
        mom = s.iloc[-1] / s.iloc[-(LOOKBACK + 1)] - 1.0
        if mom > 0:  # 绝对动量：只做正收益方向
            scored.append((c, mom))

    scored.sort(key=lambda x: x[1], reverse=True)
    picked = [c for c, _ in scored[:TOP_N]]
    gap = TOP_N - len(picked)
    return picked, gap


# ==================== 月度再平衡 ====================
def rebalance(context):
    g.attack_pool = _pit_universe(context)   # 时点构池：每月刷新真实可用进攻腿
    closes = _daily_closes(context)
    idx = _index_closes(context)
    regime = _regime(idx)

    if regime == 'defense':
        target = _defense_target(closes)
        log.info('[regime=防御] 切高股息篮子: %s'
                 % {k: round(v, 3) for k, v in target.items()})
        _order_to_target(context, target)
        _refresh_entry(context, closes)
        return

    monthly = _monthly_closes(context)
    picked, gap = _select_offense(context, closes, monthly)

    # 震荡 regime：进攻腿减半，另一半给防御，降暴露
    attack_budget = 1.0 if regime == 'attack' else 0.5

    target = {}
    if picked:
        w = _inv_vol_weights(picked, closes)
        for c, wc in w.items():
            target[c] = target.get(c, 0.0) + wc * attack_budget
    # 进攻缺口 + 震荡预留 → 全部给国债避险（不追弱腿、不满仓赌）
    reserve = (1.0 - attack_budget) + attack_budget * (gap / float(TOP_N))
    if reserve > 1e-6:
        target[SAFE_ASSET] = target.get(SAFE_ASSET, 0.0) + reserve

    log.info('[regime=%s] 选中%d腿(缺%d): %s'
             % ('进攻' if regime == 'attack' else '震荡',
                len(picked), gap, {k: round(v, 3) for k, v in target.items()}))
    _order_to_target(context, target)
    _refresh_entry(context, closes)


def _defense_target(closes):
    avail = [c for c in DEFENSE_POOL if c in closes and len(closes[c]) >= VOL_WINDOW + 1]
    if not avail:
        return {SAFE_ASSET: 1.0}
    return _inv_vol_weights(avail, closes)


def _order_to_target(context, target):
    total_value = context.portfolio.total_value
    for sec in list(context.portfolio.positions.keys()):
        if sec not in target:
            order_target_value(sec, 0)
    for sec, w in target.items():
        order_target_value(sec, total_value * w if w > 0 else 0)


def _refresh_entry(context, closes):
    """记录当前持仓的最新价，供日线 MA20 止损参考（这里止损只用MA20，不用成本）。"""
    pass  # MA20 止损不依赖成本价，保留钩子


# ==================== 日频 CLOSE 信号检查 ====================
def daily_close_check(context):
    closes = _daily_closes(context)

    # (A) 指数年线破位 → 整体切防御（最强 close 信号）
    if ENABLE_DAILY_REGIME:
        idx = _index_closes(context)
        if len(idx) >= MA_REGIME and idx.iloc[-1] < idx.iloc[-MA_REGIME:].mean():
            held_offense = [s for s in context.portfolio.positions.keys()
                            if s in ALL_ATTACK]
            if held_offense:
                target = _defense_target(closes)
                log.info('[日频·年线破位] 整体切防御: %s'
                         % {k: round(v, 3) for k, v in target.items()})
                _order_to_target(context, target)
                return

    # (B) 单腿日线跌破 MA20 → 砍到国债（快平仓，不等月度）
    if ENABLE_DAILY_STOP:
        freed_value = 0.0
        for sec in list(context.portfolio.positions.keys()):
            if sec not in ALL_ATTACK or sec == SAFE_ASSET:
                continue
            pos = context.portfolio.positions[sec]
            if pos.total_amount <= 0:
                continue
            s = closes.get(sec)
            if s is None or len(s) < MA_TIMING:
                continue
            if s.iloc[-1] <= s.iloc[-MA_TIMING:].mean():
                freed_value += pos.value
                order_target_value(sec, 0)
                log.info('[日频·MA20止损] %s 跌破%d日线，砍仓转国债' % (sec, MA_TIMING))

        # 所有被砍腿的市值一次性并入国债（读一次现值，避免循环内漂移）
        if freed_value > 0:
            cur_safe = context.portfolio.positions[SAFE_ASSET].value \
                if SAFE_ASSET in context.portfolio.positions else 0.0
            order_target_value(SAFE_ASSET, cur_safe + freed_value)
