# -*- coding: utf-8 -*-
"""
四资产再平衡 + 沪深300估值择时（聚宽回测版）

研究假设
--------
1. 基线组合：沪深300ETF、国债ETF、黄金ETF、现金各25%，每年1月再平衡。
2. 估值增强：每月用上一交易日的沪深300历史成分股计算整体PE，并与策略
   运行期间已经积累的月度PE比较；估值区间改变时，从现金向股票倾斜或反向减仓。
3. 只使用 context.previous_date 及更早的数据，信号后在下一交易日开盘交易。

实验方法
--------
先分别回测：
  EXPERIMENT = 'FOUR_ASSET_BASE'
  EXPERIMENT = 'VALUATION_TILT'
只有估值增强版在样本外改善收益、回撤和Calmar，才认为估值模块有效。

建议聚宽设置
------------
- 回测频率：日
- 起始日期：不早于2014-01-01（三只ETF均需已有可交易历史）
- 初始资金：至少100万元，降低最低佣金对结果的扭曲
- 基准：510300.XSHG

重要限制
--------
- 聚宽没有直接使用在此脚本中的官方沪深300历史PE序列。本脚本用历史成分股中
  正PE公司的总市值/利润代理值计算，口径与指数公司发布值可能不同。
- PE历史按回测过程逐月积累，至少36个月后才启用估值倾斜；预热期使用中性权重。
- 这是待证伪的研究脚本，不代表可以获得固定年化收益或控制住特定回撤。
"""

try:
    from jqdata import *
except ImportError:
    # 允许本地导入并测试纯计算函数；聚宽环境会正常提供 jqdata。
    pass

import numpy as np
import pandas as pd


# ==================== 研究配置 ====================
EXPERIMENT = 'VALUATION_TILT'  # 'FOUR_ASSET_BASE' | 'VALUATION_TILT'

CSI300_INDEX = '000300.XSHG'
EQUITY_ETF = '510300.XSHG'
BOND_ETF = '511010.XSHG'
GOLD_ETF = '518880.XSHG'
TRADED_ASSETS = [EQUITY_ETF, BOND_ETF, GOLD_ETF]

BASE_EQUITY_WEIGHT = 0.25
BASE_BOND_WEIGHT = 0.25
BASE_GOLD_WEIGHT = 0.25
BASE_CASH_WEIGHT = 0.25

EXTREME_LOW_PE_PERCENTILE = 15.0
LOW_PE_PERCENTILE = 30.0
HIGH_PE_PERCENTILE = 70.0
PE_MIN_HISTORY_MONTHS = 36
PE_LOOKBACK_MONTHS = 120
ANNUAL_REBALANCE_MONTH = 1
MIN_TRADE_WEIGHT = 0.01

# ETF双边万1、最低5元；单边滑点先按1bp，之后应做0/1/2/5bp压力测试。
COMMISSION = 0.0001
MIN_COMMISSION = 5
SLIPPAGE = 0.0001


def initialize(context):
    set_benchmark(EQUITY_ETF)
    set_option('use_real_price', True)
    set_option('avoid_future_data', True)
    set_slippage(PriceRelatedSlippage(SLIPPAGE), type='fund')
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=COMMISSION,
            close_commission=COMMISSION,
            close_today_commission=0,
            min_commission=MIN_COMMISSION,
        ),
        type='fund',
    )
    log.set_level('order', 'error')

    g.pe_history = []
    g.last_regime = None
    g.last_pe = None
    g.last_percentile = None
    g.rebalance_count = 0

    # 月初开盘只使用 previous_date 的数据生成信号并交易。
    run_monthly(
        monthly_signal,
        1,
        time='open',
        reference_security=EQUITY_ETF,
    )
    run_monthly(
        month_end_diagnostic,
        -1,
        time='after_close',
        reference_security=EQUITY_ETF,
    )

    log.info(
        'START experiment=%s | equity=%s | bond=%s | gold=%s | cash=implicit'
        % (EXPERIMENT, EQUITY_ETF, BOND_ETF, GOLD_ETF)
    )


def calculate_csi300_pe(signal_date):
    """用信号日历史成分股计算正PE公司的市值加权整体PE。"""
    stocks = get_index_stocks(CSI300_INDEX, date=signal_date)
    if not stocks:
        return None, 0

    q = query(
        valuation.code,
        valuation.pe_ratio,
        valuation.market_cap,
    ).filter(valuation.code.in_(stocks))
    df = get_fundamentals(q, date=signal_date)
    if df is None or len(df) == 0:
        return None, 0

    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    valid = df[(df['pe_ratio'] > 0) & (df['market_cap'] > 0)].copy()
    if len(valid) == 0:
        return None, 0

    # aggregate PE = sum(market cap) / sum(earnings proxy)
    total_market_cap = float(np.nansum(valid['market_cap'].values))
    earnings_proxy = float(
        np.nansum((valid['market_cap'] / valid['pe_ratio']).values)
    )
    if total_market_cap <= 0 or earnings_proxy <= 0:
        return None, 0

    aggregate_pe = total_market_cap / earnings_proxy
    return float(aggregate_pe), len(valid)


def calculate_pe_percentile(current_pe, historical_pe, minimum_history):
    """当前PE相对历史PE的百分位；历史不足时返回None。"""
    values = [
        float(value)
        for value in historical_pe
        if value is not None and np.isfinite(value) and value > 0
    ]
    if current_pe is None or not np.isfinite(current_pe) or current_pe <= 0:
        return None
    if len(values) < minimum_history:
        return None
    below_or_equal = float(
        np.count_nonzero(np.asarray(values, dtype=float) <= float(current_pe))
    )
    return 100.0 * below_or_equal / len(values)


def valuation_regime(percentile):
    if percentile is None:
        return 'neutral'
    if percentile <= EXTREME_LOW_PE_PERCENTILE:
        return 'extreme_low'
    if percentile <= LOW_PE_PERCENTILE:
        return 'low'
    if percentile <= HIGH_PE_PERCENTILE:
        return 'neutral'
    return 'high'


def target_weights(experiment, percentile):
    """返回四资产目标权重，现金通过不下单自然保留。"""
    if experiment not in ('FOUR_ASSET_BASE', 'VALUATION_TILT'):
        raise ValueError('未知EXPERIMENT=%s' % experiment)

    regime = 'neutral' if experiment == 'FOUR_ASSET_BASE' else valuation_regime(percentile)
    equity_by_regime = {
        'extreme_low': 0.50,
        'low': 0.375,
        'neutral': BASE_EQUITY_WEIGHT,
        'high': 0.125,
    }
    equity_weight = equity_by_regime[regime]
    weights = {
        EQUITY_ETF: equity_weight,
        BOND_ETF: BASE_BOND_WEIGHT,
        GOLD_ETF: BASE_GOLD_WEIGHT,
        'cash': 1.0 - equity_weight - BASE_BOND_WEIGHT - BASE_GOLD_WEIGHT,
    }
    return regime, weights


def monthly_signal(context):
    signal_date = context.previous_date
    percentile = None
    current_pe = None
    valid_count = 0

    if EXPERIMENT == 'VALUATION_TILT':
        current_pe, valid_count = calculate_csi300_pe(signal_date)
        if current_pe is None:
            log.error('%s 无法计算沪深300 PE，保持原仓位。' % signal_date)
            return

        history_values = [item['pe'] for item in g.pe_history[-PE_LOOKBACK_MONTHS:]]
        percentile = calculate_pe_percentile(
            current_pe,
            history_values,
            PE_MIN_HISTORY_MONTHS,
        )
        g.pe_history.append({'date': signal_date, 'pe': current_pe})
        if len(g.pe_history) > PE_LOOKBACK_MONTHS:
            g.pe_history = g.pe_history[-PE_LOOKBACK_MONTHS:]

    regime, weights = target_weights(EXPERIMENT, percentile)
    is_annual_rebalance = context.current_dt.month == ANNUAL_REBALANCE_MONTH
    regime_changed = g.last_regime is None or regime != g.last_regime

    g.last_pe = current_pe
    g.last_percentile = percentile

    if not is_annual_rebalance and not regime_changed:
        log.info(
            'SIGNAL %s | PE=%s | percentile=%s | regime=%s | no trade'
            % (
                signal_date,
                _format_number(current_pe),
                _format_number(percentile),
                regime,
            )
        )
        return

    if not all_assets_tradeable():
        return

    order_to_target_weights(context, weights)
    g.last_regime = regime
    g.rebalance_count += 1

    log.info(
        'REBALANCE %s | PE=%s | percentile=%s | regime=%s | '
        'target equity/bond/gold/cash=%.1f/%.1f/%.1f/%.1f | valid_pe=%d'
        % (
            signal_date,
            _format_number(current_pe),
            _format_number(percentile),
            regime,
            weights[EQUITY_ETF] * 100,
            weights[BOND_ETF] * 100,
            weights[GOLD_ETF] * 100,
            weights['cash'] * 100,
            valid_count,
        )
    )


def all_assets_tradeable():
    current_data = get_current_data()
    unavailable = []
    for security in TRADED_ASSETS:
        snapshot = current_data[security]
        if snapshot.paused or getattr(snapshot, 'stopped', False):
            unavailable.append(security)
    if unavailable:
        log.warn('以下资产不可交易，本次整体跳过调仓：%s' % unavailable)
        return False
    return True


def order_to_target_weights(context, weights):
    total_value = context.portfolio.total_value
    adjustments = []
    for security in TRADED_ASSETS:
        current_value = (
            context.portfolio.positions[security].value
            if security in context.portfolio.positions
            else 0.0
        )
        target_value = total_value * weights[security]
        difference_weight = abs(target_value - current_value) / total_value
        if difference_weight >= MIN_TRADE_WEIGHT:
            adjustments.append((security, target_value, current_value))

    # 先卖后买，降低换仓时因现金尚未释放导致的买单失败风险。
    for security, target_value, current_value in adjustments:
        if target_value < current_value:
            order_target_value(security, target_value)
    for security, target_value, current_value in adjustments:
        if target_value >= current_value:
            order_target_value(security, target_value)


def month_end_diagnostic(context):
    total_value = context.portfolio.total_value
    actual = {}
    for security in TRADED_ASSETS:
        value = (
            context.portfolio.positions[security].value
            if security in context.portfolio.positions
            else 0.0
        )
        actual[security] = value / total_value if total_value > 0 else 0.0
    cash_weight = context.portfolio.available_cash / total_value if total_value > 0 else 0.0

    record(
        equity_weight=actual[EQUITY_ETF],
        bond_weight=actual[BOND_ETF],
        gold_weight=actual[GOLD_ETF],
        cash_weight=cash_weight,
        pe_percentile=-1.0 if g.last_percentile is None else g.last_percentile,
    )
    log.info(
        'MONTH_END %s | NAV=%.2f | actual equity/bond/gold/cash='
        '%.1f/%.1f/%.1f/%.1f | rebalances=%d'
        % (
            context.current_dt.date(),
            total_value,
            actual[EQUITY_ETF] * 100,
            actual[BOND_ETF] * 100,
            actual[GOLD_ETF] * 100,
            cash_weight * 100,
            g.rebalance_count,
        )
    )


def _format_number(value):
    return 'NA' if value is None else '%.2f' % value
