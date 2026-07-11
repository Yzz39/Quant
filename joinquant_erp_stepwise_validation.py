# -*- coding: utf-8 -*-
"""
沪深300股债利差 × 中证红利ETF / 5年国债ETF：分步验证框架（聚宽）

【研究目的】
先证伪、后优化：同一份代码通过 EXPERIMENT 切换实验，不把优化项偷偷混入原版。

实验顺序：
  B1_EQUITY       100% 515080（权益买入持有基准）
  B2_60_40        固定 60% 515080 + 40% 511010（月度再平衡）
  A1_ORIGINAL     原文 4/5/6% 四档规则
  A2_HYSTERESIS   原版 + 滞回（只有 A1 成立后才测）
  A3_NO_EXTREMES  原版 + 限制极端仓位为 20%~80%（只有 A1 成立后才测）

【严格时序】
每月第一个交易日开盘：只使用 previous_date（上一交易日）的已知数据计算信号，随后交易。
沪深300盈利收益率采用其成分股“总市值加权盈利收益率”：
  EP = sum(正PE股票总市值/PE) / sum(正PE股票总市值)
  ERP = EP*100 - 10年国债收益率(%)

【外部数据要求】
在聚宽策略的“研究数据/文件”中上传文件：cn10y_yield.csv
CSV 两列：date,yield，yield 单位为百分数，例如 2.65 表示 2.65%。
脚本只使用 date <= previous_date 的最后一条，禁止未来数据；找不到数据会跳过调仓并报错。

【重要限制】
1. 515080 于 2019 年成立，实盘可交易回测建议从 2020-01-01 开始。
2. 更早历史需要指数代理，不能把今天才存在的 ETF 倒填到过去。
3. 该脚本用于策略净值比较，不模拟每月新增现金；定投应另用 XIRR 分析。
"""

from jqdata import *
import numpy as np
import pandas as pd
import io

# ==================== 只改这里 ====================
EXPERIMENT = 'A1_ORIGINAL'
BOND_YIELD_FILE = 'cn10y_yield.csv'
EQUITY_ETF = '515080.XSHG'
BOND_ETF = '511010.XSHG'
CSI300 = '000300.XSHG'

# ETF 万1、单笔最低 5 元；ETF 无印花税
COMMISSION = 0.0001
MIN_COMMISSION = 5
# 聚宽 PriceRelatedSlippage 的价格比例；先用单边 1bp，稳健性测试可改为 0/1/2/5bp
SLIPPAGE = 0.0001

LOW = 4.0
MID = 5.0
HIGH = 6.0
HYSTERESIS = 0.30
# ================================================


def initialize(context):
    set_benchmark(EQUITY_ETF)
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(PriceRelatedSlippage(SLIPPAGE), type='fund')
    set_order_cost(OrderCost(open_tax=0, close_tax=0,
                             open_commission=COMMISSION,
                             close_commission=COMMISSION,
                             close_today_commission=0,
                             min_commission=MIN_COMMISSION), type='fund')
    log.set_level('order', 'error')

    g.yield_df = load_bond_yield_file()
    g.last_equity_weight = None
    g.last_signal = None
    g.rebalance_count = 0
    g.signal_rows = []

    # 月初开盘用 previous_date 的月末数据，避免同日收盘未来函数。
    run_monthly(rebalance, 1, time='open', reference_security=EQUITY_ETF)
    run_monthly(monthly_diagnostic, -1, time='after_close', reference_security=EQUITY_ETF)

    log.info('START experiment=%s, equity=%s, bond=%s, yield_rows=%d' %
             (EXPERIMENT, EQUITY_ETF, BOND_ETF, len(g.yield_df)))


def load_bond_yield_file():
    try:
        raw = read_file(BOND_YIELD_FILE)
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8-sig')
        # 允许模板/数据文件中存在以 # 开头的说明行；空行也自动跳过。
        df = pd.read_csv(io.StringIO(raw), comment='#', skip_blank_lines=True)
        required = set(['date', 'yield'])
        if not required.issubset(set(df.columns)):
            raise ValueError('CSV 必须包含 date,yield 两列')
        df = df[['date', 'yield']].copy()
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['yield'] = pd.to_numeric(df['yield'], errors='coerce')
        df = df.dropna().sort_values('date').drop_duplicates('date', keep='last')
        if len(df) == 0:
            raise ValueError('CSV 没有有效数据')
        return df
    except Exception as e:
        log.error('无法读取 %s：%s。请上传国债收益率 CSV；本策略不会用 ETF 涨跌幅冒充收益率。' %
                  (BOND_YIELD_FILE, str(e)))
        return pd.DataFrame(columns=['date', 'yield'])


def get_latest_bond_yield(signal_date):
    if len(g.yield_df) == 0:
        return None, None
    available = g.yield_df[g.yield_df['date'] <= signal_date]
    if len(available) == 0:
        return None, None
    row = available.iloc[-1]
    # 防止错误单位：合理范围放宽到 0~15%，超过则拒绝。
    value = float(row['yield'])
    if not (0.0 < value < 15.0):
        log.error('国债收益率单位异常：%s；应填 2.65 而不是 0.0265。' % value)
        return None, None
    return value, row['date']


def get_csi300_earnings_yield(signal_date):
    stocks = get_index_stocks(CSI300, date=signal_date)
    if not stocks:
        return None, 0

    q = query(valuation.code, valuation.pe_ratio, valuation.market_cap).filter(
        valuation.code.in_(stocks)
    )
    df = get_fundamentals(q, date=signal_date)
    if df is None or len(df) == 0:
        return None, 0

    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    # 亏损股 PE 为负，不应直接进入 1/PE，否则会机械抬高或扭曲整体 EP。
    valid = df[(df['pe_ratio'] > 0) & (df['market_cap'] > 0)].copy()
    if len(valid) < 150:
        log.warn('正PE有效成分仅 %d 只，盈利收益率口径可能不稳定。' % len(valid))
    if len(valid) == 0:
        return None, 0

    earnings_cap = valid['market_cap'] / valid['pe_ratio']
    total_cap = float(np.nansum(valid['market_cap'].values))
    if total_cap <= 0:
        return None, 0
    ep = float(np.nansum(earnings_cap.values)) / total_cap
    return ep, len(valid)


def original_weight(erp):
    if erp > HIGH:
        return 1.00
    if erp > MID:
        return 0.70
    if erp > LOW:
        return 0.40
    return 0.00


def hysteresis_weight(erp, old_weight):
    # 首次运行按原始规则入档；之后跨档需要多走 HYSTERESIS，降低阈值附近反复横跳。
    if old_weight is None:
        return original_weight(erp)
    levels = [0.00, 0.40, 0.70, 1.00]
    idx = levels.index(old_weight) if old_weight in levels else 1
    up_thresholds = [LOW + HYSTERESIS, MID + HYSTERESIS, HIGH + HYSTERESIS]
    down_thresholds = [LOW - HYSTERESIS, MID - HYSTERESIS, HIGH - HYSTERESIS]

    while idx < 3 and erp > up_thresholds[idx]:
        idx += 1
    while idx > 0 and erp <= down_thresholds[idx - 1]:
        idx -= 1
    return levels[idx]


def choose_weight(erp):
    if EXPERIMENT == 'B1_EQUITY':
        return 1.00
    if EXPERIMENT == 'B2_60_40':
        return 0.60
    if EXPERIMENT == 'A1_ORIGINAL':
        return original_weight(erp)
    if EXPERIMENT == 'A2_HYSTERESIS':
        return hysteresis_weight(erp, g.last_equity_weight)
    if EXPERIMENT == 'A3_NO_EXTREMES':
        # jqdata 的星号导入可能覆盖 Python 内置 min/max，使用 numpy 避免污染。
        return float(np.minimum(0.80, np.maximum(0.20, original_weight(erp))))
    raise ValueError('未知 EXPERIMENT=%s' % EXPERIMENT)


def is_tradeable(security):
    current = get_current_data()[security]
    if current.paused:
        log.warn('%s 停牌，跳过本次调仓。' % security)
        return False
    return True


def rebalance(context):
    signal_date = context.previous_date

    # 基准策略无需 ERP 也能运行；其余实验必须拿到真实 ERP。
    if EXPERIMENT in ('B1_EQUITY', 'B2_60_40'):
        ep, n = None, 0
        bond_yield, yield_date = None, None
        erp = None
    else:
        ep, n = get_csi300_earnings_yield(signal_date)
        bond_yield, yield_date = get_latest_bond_yield(signal_date)
        if ep is None or bond_yield is None:
            log.error('%s 信号缺失，保持原仓位；ep=%s, bond_yield=%s' %
                      (signal_date, str(ep), str(bond_yield)))
            return
        # CSV 中国债收益率为百分数；EP 从小数转为百分数。
        erp = ep * 100.0 - bond_yield

    target_equity = choose_weight(erp)
    target_bond = 1.0 - target_equity

    if not is_tradeable(EQUITY_ETF) or not is_tradeable(BOND_ETF):
        return

    total = context.portfolio.total_value
    # 先卖后买，减少满仓换仓时现金不足；order_target_value 包含当前价格下的目标市值。
    current_eq = context.portfolio.positions[EQUITY_ETF].value if EQUITY_ETF in context.portfolio.positions else 0.0
    current_bd = context.portfolio.positions[BOND_ETF].value if BOND_ETF in context.portfolio.positions else 0.0
    targets = [(EQUITY_ETF, total * target_equity, current_eq),
               (BOND_ETF, total * target_bond, current_bd)]
    for security, target, current in targets:
        if target < current:
            order_target_value(security, target)
    for security, target, current in targets:
        if target >= current:
            order_target_value(security, target)

    g.last_equity_weight = target_equity
    g.rebalance_count += 1
    g.last_signal = {
        'date': str(signal_date), 'ep_pct': None if ep is None else ep * 100.0,
        'bond_yield_pct': bond_yield, 'yield_date': str(yield_date), 'erp_pct': erp,
        'equity_weight': target_equity, 'bond_weight': target_bond,
        'valid_pe_count': n
    }
    g.signal_rows.append(g.last_signal.copy())

    log.info('SIGNAL %s | EP=%s%% | CN10Y=%s%%(%s) | ERP=%s%% | target=%d/%d | N=%d' %
             (signal_date,
              'NA' if ep is None else ('%.3f' % (ep * 100.0)),
              'NA' if bond_yield is None else ('%.3f' % bond_yield),
              str(yield_date), 'NA' if erp is None else ('%.3f' % erp),
              int(target_equity * 100), int(target_bond * 100), n))


def monthly_diagnostic(context):
    eq_value = context.portfolio.positions[EQUITY_ETF].value if EQUITY_ETF in context.portfolio.positions else 0.0
    bd_value = context.portfolio.positions[BOND_ETF].value if BOND_ETF in context.portfolio.positions else 0.0
    total = context.portfolio.total_value
    eq_actual = eq_value / total if total > 0 else 0
    bd_actual = bd_value / total if total > 0 else 0
    record(eq_weight=eq_actual, bond_weight=bd_actual,
           erp=0 if g.last_signal is None or g.last_signal['erp_pct'] is None else g.last_signal['erp_pct'])
    log.info('MONTH_END %s | NAV=%.2f | actual=%0.1f/%0.1f | rebalances=%d' %
             (context.current_dt.date(), total, eq_actual * 100, bd_actual * 100, g.rebalance_count))
