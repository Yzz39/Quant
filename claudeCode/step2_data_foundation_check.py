# -*- coding: utf-8 -*-
# =====================================================================
# 步骤1｜数据地基 + 时点标的池 自检脚本（聚宽 JoinQuant）
# ---------------------------------------------------------------------
# 核心逻辑：这个脚本【不产 alpha、不下单】，只回答步骤1闸门的五个勾选框：
#   1. 价格口径对不对（后复权，除息缺口不被误判破位）
#   2. 有没有未来函数（一律 context.previous_date 取价）
#   3. 标的池是不是「当时真实存在」的（PIT，规避幸存者偏差）
#   4. 全候选池缺失率 < 2%
#   5. 有效回测起点是哪年（行业腿攒够 MA250 历史）
#
# 用法：在聚宽新建【回测】，区间设 2014-01-01 ~ 至今，跑一次看 log 即可。
#      不产生持仓，日志打完 initialize 段就是全部结论。
# 基调版 v0：先跑通、看数，阈值和采样时点你自己在配置区改。
# =====================================================================
import datetime
import numpy as np
import pandas as pd
from jqdata import *   # 注意：会覆盖内置 sum，数值运算用 np.nansum / np.nanmax

# ==================== 配置区（改这里） ====================
# —— 与主策略 etf_rotation_s3s4_joinquant.py 完全一致的候选池，别各写一套 ——
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
BROAD_CANDIDATES = [
    '510050.XSHG',  # 上证50   (2004)
    '510300.XSHG',  # 沪深300  (2012)
    '510500.XSHG',  # 中证500  (2013)
    '159915.XSHE',  # 创业板   (2011)
    '159901.XSHE',  # 深100    (2006)
    '518880.XSHG',  # 黄金     (2013)
    '513100.XSHG',  # 纳指     (2013, QDII)
]
ALL_ATTACK = SECTOR_CANDIDATES + BROAD_CANDIDATES

# PIT 阈值（与主策略一致）
MIN_LIST_DAYS   = 400   # 上市满多少自然日才够入池
MIN_SECTOR_LEGS = 5     # 行业腿够这么多才算「行业轮动有效」

# 自检阈值（步骤1闸门）
MISSING_TOL     = 0.02  # 缺失率上限 2%
MA_REGIME       = 250   # 行业腿要攒够的历史（判有效起点）

# PIT 回放采样时点（你想加就加，看降级→行业的切换）
PIT_SAMPLE_DATES = ['2014-06-30', '2016-06-30', '2019-06-30',
                    '2022-06-30', '2025-06-30']

# 除息缺口检查：挑一只有分红历史的宽基/红利腿
DIV_CHECK_CODE  = '510300.XSHG'


# ==================== 聚宽入口 ====================
def initialize(context):
    set_option('avoid_future_data', True)   # 硬关未来函数
    set_option('use_real_price', True)      # 后复权口径
    log.info('=' * 60)
    log.info('步骤1 数据地基自检开始（不下单，只诊断）')
    log.info('=' * 60)

    _check_missing_rate(context)      # 闸门4：缺失率
    _check_dividend_gap(context)      # 闸门2：后复权除息缺口
    _replay_pit_universe()            # 闸门3+5：PIT 回放 + 有效起点
    _check_future_data_hint()         # 闸门2：未来函数自查清单（人工核对项）

    log.info('=' * 60)
    log.info('步骤1 自检结束：以上五项全绿才准进步骤2')
    log.info('=' * 60)


def handle_data(context, data):
    pass  # 本脚本不交易


# ==================== 闸门4：缺失率 ====================
def _check_missing_rate(context):
    """逐腿打印起止日期 + NaN 占比，任何一腿 > MISSING_TOL 就标红。"""
    log.info('---- [闸门4] 全候选池缺失率（阈值 < %.0f%%）----' % (MISSING_TOL * 100))
    end = context.previous_date
    codes = ALL_ATTACK
    # 取足够长历史（从各腿上市起）
    df = get_price(codes, end_date=end, frequency='daily',
                   fields=['close'], skip_paused=False,
                   fq='post', count=3000, panel=False)
    bad = []
    for c in codes:
        sub = df[df['code'] == c] if 'code' in df.columns else None
        if sub is None or len(sub) == 0:
            log.warn('  %s  无数据（可能未上市/退市）' % c)
            bad.append(c)
            continue
        n = len(sub)
        miss = float(np.mean(pd.isnull(sub['close'].values)))
        d0 = sub['time'].iloc[0] if 'time' in sub.columns else '?'
        flag = '  <<< 超标' if miss > MISSING_TOL else ''
        log.info('  %s  起=%s  样本=%d  缺失=%.2f%%%s'
                 % (c, str(d0)[:10], n, miss * 100, flag))
        if miss > MISSING_TOL:
            bad.append(c)
    if bad:
        log.warn('[闸门4] 未过：以下腿缺失超标/无数据 → 剔除或缩短区间: %s' % bad)
    else:
        log.info('[闸门4] 通过：全候选池缺失率均 < %.0f%%' % (MISSING_TOL * 100))


# ==================== 闸门2：后复权除息缺口 ====================
def _check_dividend_gap(context):
    """后复权下，除息不该造成大跳空。打印最大单日跌幅，人工确认没有假破位。"""
    log.info('---- [闸门2a] 后复权除息缺口检查（标的 %s）----' % DIV_CHECK_CODE)
    end = context.previous_date
    df = get_price(DIV_CHECK_CODE, end_date=end, frequency='daily',
                   fields=['close'], fq='post', count=2000)
    if df is None or len(df) < 2:
        log.warn('  取价失败，跳过')
        return
    ret = df['close'].pct_change().dropna()
    worst = ret.nsmallest(5)
    log.info('  最大单日跌幅 Top5（后复权）:')
    for t, r in worst.items():
        log.info('    %s  %.2f%%' % (str(t)[:10], r * 100))
    log.info('  说明：若某日 -8%%~-10%% 且当天是除息日，多半是复权没对；'
             '后复权正确时除息缺口应被抹平。请人工对照该腿分红日历。')


# ==================== 闸门3+5：PIT 回放 + 有效起点 ====================
def _replay_pit_universe():
    """对每个采样时点跑一遍时点构池，打印入池腿数/名单/是否降级。
       第一个「行业腿 >= MIN_SECTOR_LEGS 且已攒够 MA_REGIME 历史」的时点
       ≈ 行业轮动有效起点。"""
    log.info('---- [闸门3+5] PIT 时点构池回放（幸存者偏差 + 有效起点）----')
    first_industry_date = None
    for ds in PIT_SAMPLE_DATES:
        d = datetime.datetime.strptime(ds, '%Y-%m-%d').date()
        pool, tier, n_sector = _pit_at(d)
        # 有效起点：行业层成军 + 最老行业腿已满 MA250 交易日
        enough_hist = _sector_history_ready(d)
        mark = ''
        if tier == '行业' and enough_hist and first_industry_date is None:
            first_industry_date = ds
            mark = '   <<< 行业轮动有效起点候选'
        log.info('  [%s] 入池%d腿[%s] 行业腿=%d hist够=%s%s'
                 % (ds, len(pool), tier, n_sector, enough_hist, mark))
        log.info('        名单: %s' % pool)
    if first_industry_date:
        log.info('[闸门5] 有效起点判定 ≈ %s（此前只能做宽基/风格轮动）'
                 % first_industry_date)
    else:
        log.info('[闸门5] 采样时点内未见「纯行业且历史足」→ 加密采样或确认仍需降级')


def _pit_at(d):
    """复刻主策略 _pit_universe 逻辑，但用显式日期 d（研究态回放）。"""
    try:
        allsec = get_all_securities(types=['etf'], date=d)
        exist = set(allsec.index)
    except Exception as e:
        log.warn('  get_all_securities(%s) 失败，回退全候选: %s' % (d, e))
        exist, allsec = set(ALL_ATTACK), None

    cutoff = d - datetime.timedelta(days=MIN_LIST_DAYS)

    def _eligible(cands):
        out = []
        for c in cands:
            if c not in exist:
                continue
            if allsec is not None and c in allsec.index:
                sd = allsec.at[c, 'start_date']
                if pd.Timestamp(sd).date() > cutoff:
                    continue
            out.append(c)
        return out

    sectors = _eligible(SECTOR_CANDIDATES)
    if len(sectors) >= MIN_SECTOR_LEGS:
        return sectors, '行业', len(sectors)
    pool = sectors + _eligible(BROAD_CANDIDATES)
    return pool, '宽基降级', len(sectors)


def _sector_history_ready(d):
    """最老的几只行业腿在 d 之前是否已有 >= MA_REGIME 个交易日历史。"""
    try:
        allsec = get_all_securities(types=['etf'], date=d)
    except Exception:
        return False
    ready = 0
    for c in SECTOR_CANDIDATES:
        if c in allsec.index:
            sd = pd.Timestamp(allsec.at[c, 'start_date']).date()
            # 粗算：MA_REGIME 个交易日 ≈ MA_REGIME*1.45 自然日
            if (d - sd).days >= int(MA_REGIME * 1.45):
                ready += 1
    return ready >= MIN_SECTOR_LEGS


# ==================== 闸门2b：未来函数人工核对清单 ====================
def _check_future_data_hint():
    log.info('---- [闸门2b] 未来函数自查清单（人工核对主策略代码）----')
    log.info('  [ ] set_option("avoid_future_data", True) 已开')
    log.info('  [ ] 盘中决策取价一律用 context.previous_date，不碰当日 close')
    log.info('  [ ] run_monthly/run_daily 的触发点在收盘后或用昨收判定')
    log.info('  [ ] grep 主策略：无 attribute_history 越界 / 无当日 close 进信号')
