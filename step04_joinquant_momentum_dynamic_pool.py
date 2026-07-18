# -*- coding: utf-8 -*-
"""
脚本功能：在聚宽上验证“动态ETF池 + 单一ETF持仓”的可配置频率动量轮动策略。
标的范围：每个信号日查询当时存在的全市场ETF，排除特殊结构和现金类重复产品，
          通过上市期、数据完整性、类别覆盖、成交额和收益相关性构建动态风险ETF池；货币ETF
          仅作为单独的防守与现金替代标的。
信号时序：调仓周期和ETF池刷新周期分别由独立参数控制，均按A股交易日计数；
          评分只使用信号日及以前的数据，订单最早在下一交易日执行。
调仓执行：M0至M3G模式最终只持有一只ETF；保留equal_weight作为兼容诊断模式；
          次日09:30先卖、09:35后买，失败订单最多重试3个交易日。
主要风控：上市满252个交易日、最近60日流动性门槛、类别覆盖、Pearson/Spearman相关性去重、绝对动量
          或因子正值过滤、停牌和涨跌停检查、成交量比例限制、佣金与滑点。
研究功能：保留M0-M3G评分模式和equal_weight诊断模式、未来21日标签、订单成交审计
          和账户恒等式检查。
研究区间：沿用Step04预注册口径，默认训练区间为2015-01-01至2020-12-31；
          如需样本外验证，应另建版本修改区间，不能看完结果后移动边界。
适用限制：基金名称过滤不能替代底层指数与历史规模审计；跨境ETF仍包含交易时区、
          汇率和溢折价影响。本脚本用于回测验证，不代表实盘收益保证。

评分模式：
M0=momentum，M1=m1_absolute，M2=m2_recent_confirm，
M2R=m2_ranked_recent，M3A=m3_ols_slope，M3B=m3b_efficiency，
M3C=m3c_bias_trend，M3D=m3d_wls_slope，M3E=m3e_huber_slope，
M3F=m3f_equal_rank，M3G=m3g_efficiency_rank。
"""

# 版本边界：本文件以 step04_joinquant_momentum_baseline.py 为基线，
# 将固定 CORE 候选范围替换为动态ETF池，并将调仓周期、池刷新周期设为独立参数；订单执行、因子公式和标签审计沿用基线。
from jqdata import *
import builtins
import datetime
import math

import pandas as pd


# from jqdata import * 可能覆盖Python内置聚合函数；动态池逻辑固定使用原生实现。
_py_any = builtins.any
_py_max = builtins.max
_py_min = builtins.min
_py_sum = builtins.sum

# jqdata部分版本会导出同名聚合函数；本策略不使用这些查询聚合，恢复Python内置实现。
any = _py_any
max = _py_max
min = _py_min
sum = _py_sum


RUN_MODE = "m3_ols_slope"
ENGINE_VERSION = "dynamic_pool_category_coverage_v0.8_pearson_spearman"
CODE_VERSION = "%s_engine_%s" % (RUN_MODE, ENGINE_VERSION)
CASH_SECURITY = "511880.XSHG"
M3_SELECTION_POLICY = "ranked_factor_only"

SIGNAL_MODES = (
    "momentum",
    "m1_absolute",
    "m2_recent_confirm",
    "m2_ranked_recent",
    "m3_ols_slope",
    "m3b_efficiency",
    "m3c_bias_trend",
    "m3d_wls_slope",
    "m3e_huber_slope",
    "m3f_equal_rank",
    "m3g_efficiency_rank",
)
M3_MODES = (
    "m3_ols_slope",
    "m3b_efficiency",
    "m3c_bias_trend",
    "m3d_wls_slope",
    "m3e_huber_slope",
    "m3f_equal_rank",
    "m3g_efficiency_rank",
)
RECENT_FILTER_MODES = ("m2_recent_confirm",)
RANKED_RECENT_MODES = ("m2_ranked_recent",)
RANKED_FACTOR_MODES = M3_MODES

# =========================== 动态ETF池配置 ===========================
# 先以可交易性和相关性构池，再交给下方动量因子评分，避免同一收益信号既选池又择时。
LOOKBACK = 126
RECENT_LOOKBACK = 21
CORRELATION_DAYS = 126
MIN_CORRELATION_OBSERVATIONS = 80
MIN_DUPLICATE_CORRELATION = 0.00
MAX_DUPLICATE_CORRELATION = 0.80
MAX_LIQUID_CANDIDATES = 100
MAX_DYNAMIC_RISK_POOL_SIZE = 25
MIN_DYNAMIC_RISK_ASSETS = 5
DYNAMIC_DATA_CHUNK_SIZE = 180
# 两个周期独立配置，单位均为A股交易日：1=日频，5=周频，10=双周，20≈月频。
REBALANCE_INTERVAL = 5
POOL_REFRESH_INTERVAL = 5

# 部分聚宽版本的历史etf查询返回不完整，合并etf/lof后再按行类型和名称排除LOF。
ETF_QUERY_TYPES = ["etf", "lof"]

# 这些产品不进入风险ETF排名；货币ETF由CASH_SECURITY单独加入。
EXCLUDED_NAME_KEYWORDS = (
    "LOF",
    "分级",
    "杠杆",
    "反向",
    "做空",
    "两倍",
    "2倍",
    "三倍",
    "联接",
)
CASH_NAME_KEYWORDS = (
    "货币",
    "现金",
    "添益",
    "理财金",
    "保证金",
)

# ============================== 资产类别配置 ==============================
ETF_CATEGORY_ORDER = (
    "broad_equity",
    "cross_border_equity",
    "industry_theme",
    "dividend_style",
    "bond",
    "commodity",
    "cash",
)
RISK_CATEGORY_ORDER = tuple(
    category for category in ETF_CATEGORY_ORDER if category != "cash"
)
CATEGORY_MIN_REPRESENTATIVES = {
    category: 1 for category in ETF_CATEGORY_ORDER
}
CATEGORY_LABELS = {
    "broad_equity": "宽基权益",
    "cross_border_equity": "跨境权益",
    "industry_theme": "行业主题",
    "dividend_style": "红利风格",
    "bond": "债券",
    "commodity": "商品黄金",
    "cash": "货币现金",
}
BROAD_EQUITY_SECURITY_OVERRIDES = (
    "510050.XSHG",
    "510180.XSHG",
    "510300.XSHG",
    "510310.XSHG",
    "510330.XSHG",
    "510500.XSHG",
    "510510.XSHG",
    "159901.XSHE",
    "159902.XSHE",
    "159915.XSHE",
    "159919.XSHE",
    "159922.XSHE",
)

# ============================== 因子配置 ==============================
HUBER_EPSILON = 1.345
HUBER_MAX_ITERATIONS = 50
HUBER_TOLERANCE = 1e-10
FUSION_FACTORS = ("huber", "efficiency", "bias")
ELIGIBILITY_DAYS = 252
LIQUIDITY_DAYS = 60
MIN_AVG_MONEY = 50_000_000.0
LABEL_HORIZON = 21
ROUND_TRIP_COST = 0.0014
LABEL_MIN_NET_RETURN = 0.01
LABEL_MAX_MAE = -0.05
COMMISSION = 0.0002
SLIPPAGE = 0.0005
INITIAL_CAPITAL = 100_000.0
TRAIN_START = datetime.date(2015, 1, 1)
TRAIN_END = datetime.date(2020, 12, 31)
DATA_FIELDS = ["open", "high", "low", "close", "volume", "money"]

# 流动性测试版本：L0为原固定门槛控制组，L3为主测试版本；与独立池验证器保持一致。
LIQUIDITY_MODE = "L3"
LIQUIDITY_QUANTILE = 0.30
LIQUIDITY_CAPITAL_LEVERAGE = 1.0
MAX_PARTICIPATION = 0.02
LIQUIDITY_BUFFER = 1.2
ABSOLUTE_LIQUIDITY_FLOOR = 3_000_000.0
MIN_ACTIVE_DAYS_RATIO = 0.95


# =========================== 初始化与回测配置 ===========================

def initialize(context):
    if RUN_MODE not in SIGNAL_MODES + ("equal_weight",):
        raise ValueError(
            "unsupported RUN_MODE: %s" % RUN_MODE
        )
    if LIQUIDITY_MODE not in ("L0", "L3"):
        raise ValueError("unsupported LIQUIDITY_MODE: %s" % LIQUIDITY_MODE)

    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)
    # 订单成交量限制与L3流动性容量假设保持一致。
    set_option("order_volume_ratio", MAX_PARTICIPATION)
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=COMMISSION,
            close_commission=COMMISSION,
            min_commission=5,
        ),
        type="fund",
    )
    set_slippage(PriceRelatedSlippage(SLIPPAGE), type="fund")

    g.mode = RUN_MODE
    g.pending = None
    g.baseline_started = False
    g.first_signal_logged = False
    g.labels = []
    g.logged_orders = set()
    g.logged_trades = set()
    g.last_position_signature = None
    g.config_logged = False
    g.signal_count = 0
    g.label_total = 0
    g.label_success = 0
    g.selected_label_total = 0
    g.selected_label_success = 0
    g.selected_net_sum = 0.0
    g.last_pool_diagnostics = {}
    g.last_pool_names = {}
    g.rebalance_dates = _build_cycle_dates(REBALANCE_INTERVAL)
    g.pool_refresh_dates = _build_cycle_dates(POOL_REFRESH_INTERVAL)
    g.pool_cache = None
    g.pool_cache_date = None

    starting_cash = context.portfolio.starting_cash
    log.info(
        "S04_CODE_VERSION %s liquidity_mode=%s"
        % (CODE_VERSION, LIQUIDITY_MODE)
    )
    log.info(
        "S04_CONFIG mode=%s selection_policy=%s capital=%.2f lookback=%d recent_lookback=%d label_horizon=%d "
        "label_min_net=%.4f label_max_mae=%.4f huber_epsilon=%.3f huber_max_iter=%d "
        "train_start=%s train_end=%s rebalance_interval=%d pool_refresh_interval=%d "
        "rebalance_dates=%d pool_refresh_dates=%d dynamic_pool_max=%d "
        "min_risk_assets=%d corr_floor=%.2f corr_cap=%.2f "
        "corr_methods=pearson_spearman liquidity_mode=%s min_avg_money=%.2f "
        "liquidity_quantile=%.2f capital_leverage=%.2f max_participation=%.4f "
        "liquidity_buffer=%.2f absolute_floor=%.2f active_days_ratio=%.2f"
        % (
            g.mode,
            M3_SELECTION_POLICY if g.mode in M3_MODES else "mode_default",
            starting_cash,
            LOOKBACK,
            RECENT_LOOKBACK,
            LABEL_HORIZON,
            LABEL_MIN_NET_RETURN,
            LABEL_MAX_MAE,
            HUBER_EPSILON,
            HUBER_MAX_ITERATIONS,
            TRAIN_START,
            TRAIN_END,
            REBALANCE_INTERVAL,
            POOL_REFRESH_INTERVAL,
            len(g.rebalance_dates),
            len(g.pool_refresh_dates),
            MAX_DYNAMIC_RISK_POOL_SIZE,
            MIN_DYNAMIC_RISK_ASSETS,
            MIN_DUPLICATE_CORRELATION,
            MAX_DUPLICATE_CORRELATION,
            LIQUIDITY_MODE,
            MIN_AVG_MONEY,
            LIQUIDITY_QUANTILE,
            LIQUIDITY_CAPITAL_LEVERAGE,
            MAX_PARTICIPATION,
            LIQUIDITY_BUFFER,
            ABSOLUTE_LIQUIDITY_FLOOR,
            MIN_ACTIVE_DAYS_RATIO,
        )
    )
    if abs(starting_cash - INITIAL_CAPITAL) > 0.01:
        log.error(
            "S04_CAPITAL_MISMATCH expected=%.2f actual=%.2f"
            % (INITIAL_CAPITAL, starting_cash)
        )
    else:
        log.info("S04_CAPITAL expected=%.2f actual=%.2f" % (INITIAL_CAPITAL, starting_cash))

    run_daily(execute_sells, time="09:30")
    run_daily(execute_buys, time="09:35")
    run_daily(after_close_audit, time="after_close")


# ========================= 5日信号与单持仓决策 =========================

def after_close_audit(context):
    today = context.current_dt.date()
    _update_mature_labels(today)

    if today < TRAIN_END:
        if today in g.pool_refresh_dates:
            _refresh_pool_cache(today)
        if today in g.rebalance_dates:
            _generate_signal(context, today)

    _expire_unfilled_signal(context)
    _log_new_orders_and_trades()
    _log_eod(context)


def _generate_signal(context, signal_date):
    if g.pending is not None:
        log.info("S04_SIGNAL_SKIPPED date=%s reason=pending_order" % signal_date)
        return

    (
        eligible,
        scores,
        recent_scores,
        reasons,
        avg_money,
        slope_scores,
        r2_scores,
        path_returns,
        efficiency_ratios,
        bias_trend_slopes,
        factor_metadata,
    ) = _eligible_universe(signal_date)
    pool_diagnostics = g.last_pool_diagnostics
    pool_issues = pool_diagnostics.get("issues", [])
    if pool_issues:
        # 构池数据不完整时保留现有持仓，不把一次查询失败误当成卖出信号。
        log.info(
            "S04_SIGNAL_SKIPPED date=%s reason=dynamic_pool_invalid issues=%s diagnostics=%s"
            % (signal_date, pool_issues, pool_diagnostics)
        )
        return
    if not g.baseline_started:
        risk_assets = [
            security for security in eligible
            if security != CASH_SECURITY
        ]
        if (
            len(risk_assets) < MIN_DYNAMIC_RISK_ASSETS
            or CASH_SECURITY not in eligible
        ):
            log.info(
                "S04_WAIT_DYNAMIC_POOL date=%s risk_count=%d required=%d "
                "cash_available=%s diagnostics=%s score_reasons=%s"
                % (
                    signal_date,
                    len(risk_assets),
                    MIN_DYNAMIC_RISK_ASSETS,
                    CASH_SECURITY in eligible,
                    g.last_pool_diagnostics,
                    reasons,
                )
            )
            return
        g.baseline_started = True
        log.info(
            "S04_BASELINE_START date=%s risk_count=%d dynamic_pool=%s"
            % (signal_date, len(risk_assets), eligible)
        )

    if not eligible:
        target = {}
        selected = None
        selected_rank = None
        excluded = []
    elif g.mode in RANKED_FACTOR_MODES:
        result = _ranked_factor_target(scores, recent_scores)
        selected = result["selected"]
        selected_rank = result["selected_rank"]
        excluded = result["excluded"]
        absolute_pass = result["absolute_pass"]
        recent_score = result["recent_score"]
        recent_pass = result["recent_pass"]
        decision = result["decision"]
        target = result["target"]
    elif g.mode in RANKED_RECENT_MODES:
        result = _ranked_recent_target(scores, recent_scores)
        selected = result["selected"]
        selected_rank = result["selected_rank"]
        excluded = result["excluded"]
        absolute_pass = result["absolute_pass"]
        recent_score = result["recent_score"]
        recent_pass = result["recent_pass"]
        decision = result["decision"]
        target = result["target"]
    elif g.mode in SIGNAL_MODES:
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        selected = ranked[0][0]
        selected_rank = 1
        excluded = []
        absolute_pass = scores[selected] > 0.0
        recent_score = recent_scores[selected]
        recent_pass = recent_score > 0.0
        if g.mode in RECENT_FILTER_MODES and selected == CASH_SECURITY:
            target = {CASH_SECURITY: 1.0}
            decision = "cash_top1"
        elif g.mode in RECENT_FILTER_MODES and (not absolute_pass or not recent_pass):
            if CASH_SECURITY in eligible:
                target = {CASH_SECURITY: 1.0}
                decision = "recent_filter" if absolute_pass else "cash_filter"
            else:
                target = {}
                decision = "cash_unavailable"
        elif g.mode == "m1_absolute" and not absolute_pass:
            if CASH_SECURITY in eligible:
                target = {CASH_SECURITY: 1.0}
                decision = "cash_filter"
            else:
                target = {}
                decision = "cash_unavailable"
        else:
            target = {selected: 1.0}
            decision = "top1"
    else:
        selected = None
        selected_rank = None
        excluded = []
        absolute_pass = None
        recent_score = None
        recent_pass = None
        decision = "equal_weight"
        weight = 1.0 / len(eligible)
        target = {security: weight for security in sorted(eligible)}

    if not eligible:
        absolute_pass = None
        recent_score = None
        recent_pass = None
        decision = "no_eligible_asset"

    g.signal_count += 1
    score_text = ";".join(
        "%s:%.8f" % (security, scores[security]) for security in sorted(scores)
    )
    recent_score_text = ";".join(
        "%s:%.8f" % (security, recent_scores[security]) for security in sorted(recent_scores)
    )
    target_text = ";".join(
        "%s:%.8f" % (security, target[security]) for security in sorted(target)
    )
    log.info(
        "S04_SIGNAL date=%s mode=%s selected=%s selected_rank=%s excluded=%s absolute_pass=%s "
        "recent_score=%s recent_pass=%s decision=%s eligible=%s scores=%s recent_scores=%s target=%s"
        % (
            signal_date,
            g.mode,
            selected,
            selected_rank,
            excluded,
            absolute_pass,
            recent_score,
            recent_pass,
            decision,
            eligible,
            score_text,
            recent_score_text,
            target_text,
        )
    )
    if selected is not None:
        selected_name = g.last_pool_names.get(selected, "")
        log.info(
            "S04_SELECTED date=%s security=%s name=%s rank=%s score=%.8f"
            % (signal_date, selected, selected_name, selected_rank, scores[selected])
        )
        log.info(
            "S04_FACTOR_DETAIL date=%s security=%s score=%.8f slope=%s r2=%s "
            "path_return=%s efficiency_ratio=%s bias_trend_slope=%s huber_iterations=%s "
            "huber_downweighted=%s huber_score=%s efficiency_score=%s bias_score=%s "
            "huber_rank=%s efficiency_rank=%s bias_rank=%s"
            % (
                signal_date,
                selected,
                scores[selected],
                "%.10f" % slope_scores[selected] if selected in slope_scores else "NA",
                "%.8f" % r2_scores[selected] if selected in r2_scores else "NA",
                "%.10f" % path_returns[selected] if selected in path_returns else "NA",
                "%.8f" % efficiency_ratios[selected] if selected in efficiency_ratios else "NA",
                "%.10f" % bias_trend_slopes[selected] if selected in bias_trend_slopes else "NA",
                factor_metadata.get(selected, {}).get("huber_iterations", "NA"),
                factor_metadata.get(selected, {}).get("huber_downweighted", "NA"),
                factor_metadata.get(selected, {}).get("huber_score", "NA"),
                factor_metadata.get(selected, {}).get("efficiency_score", "NA"),
                factor_metadata.get(selected, {}).get("bias_score", "NA"),
                factor_metadata.get(selected, {}).get("huber_rank", "NA"),
                factor_metadata.get(selected, {}).get("efficiency_rank", "NA"),
                factor_metadata.get(selected, {}).get("bias_rank", "NA"),
            )
        )

    gap = 0.0
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    if len(ranked) >= 2:
        gap = ranked[0][1] - ranked[1][1]
    for security in eligible:
        g.labels.append(
            {
                "signal_date": signal_date,
                "security": security,
                "score": scores[security],
                "selected": int(
                    g.mode in SIGNAL_MODES
                    and security == selected
                    and target.get(security, 0.0) > 0.0
                ),
                "selected_rank": selected_rank if security == selected else None,
                "gap": (
                    gap
                    if g.mode in SIGNAL_MODES
                    and security == selected
                    and target.get(security, 0.0) > 0.0
                    else None
                ),
                "recent_score": recent_scores[security],
                "recent_pass": recent_scores[security] > 0.0,
                "slope": slope_scores.get(security),
                "r2": r2_scores.get(security),
                "path_return": path_returns.get(security),
                "efficiency_ratio": efficiency_ratios.get(security),
                "bias_trend_slope": bias_trend_slopes.get(security),
                "huber_iterations": factor_metadata.get(security, {}).get("huber_iterations"),
                "huber_downweighted": factor_metadata.get(security, {}).get("huber_downweighted"),
                "huber_score": factor_metadata.get(security, {}).get("huber_score"),
                "efficiency_score": factor_metadata.get(security, {}).get("efficiency_score"),
                "bias_score": factor_metadata.get(security, {}).get("bias_score"),
                "huber_rank": factor_metadata.get(security, {}).get("huber_rank"),
                "efficiency_rank": factor_metadata.get(security, {}).get("efficiency_rank"),
                "bias_rank": factor_metadata.get(security, {}).get("bias_rank"),
            }
        )

    if not g.first_signal_logged:
        g.first_signal_logged = True
        log.info("S04_FIRST_SIGNAL date=%s next_execution=next_trade_day" % signal_date)
    g.pending = {
        "signal_date": signal_date,
        "target": target,
        "target_amounts": None,
        "attempts": 0,
        "last_attempt": None,
    }


def _ranked_recent_target(long_scores, recent_scores):
    """Walk a factor ranking until a positive-score, positive-recent candidate passes."""
    ranked = sorted(long_scores.items(), key=lambda item: (-item[1], item[0]))
    excluded = []
    for rank, (security, long_score) in enumerate(ranked, start=1):
        if security == CASH_SECURITY:
            return {
                "selected": security,
                "selected_rank": rank,
                "excluded": excluded,
                "absolute_pass": long_score > 0.0,
                "recent_score": recent_scores[security],
                "recent_pass": recent_scores[security] > 0.0,
                "decision": "cash_ranked",
                "target": {security: 1.0},
            }
        recent_score = recent_scores[security]
        if long_score > 0.0 and recent_score > 0.0:
            return {
                "selected": security,
                "selected_rank": rank,
                "excluded": excluded,
                "absolute_pass": True,
                "recent_score": recent_score,
                "recent_pass": True,
                "decision": "ranked_recent_pass",
                "target": {security: 1.0},
            }
        excluded.append(security)

    if CASH_SECURITY in long_scores:
        cash_rank = next(
            rank
            for rank, (security, _) in enumerate(ranked, start=1)
            if security == CASH_SECURITY
        )
        return {
            "selected": CASH_SECURITY,
            "selected_rank": cash_rank,
            "excluded": excluded,
            "absolute_pass": long_scores[CASH_SECURITY] > 0.0,
            "recent_score": recent_scores[CASH_SECURITY],
            "recent_pass": recent_scores[CASH_SECURITY] > 0.0,
            "decision": "cash_fallback",
            "target": {CASH_SECURITY: 1.0},
        }
    return {
        "selected": None,
        "selected_rank": None,
        "excluded": excluded,
        "absolute_pass": False,
        "recent_score": None,
        "recent_pass": False,
        "decision": "cash_unavailable",
        "target": {},
    }


def _ranked_factor_target(long_scores, recent_scores):
    """Walk a factor ranking without using recent momentum as a gate."""
    ranked = sorted(long_scores.items(), key=lambda item: (-item[1], item[0]))
    excluded = []
    for rank, (security, long_score) in enumerate(ranked, start=1):
        recent_score = recent_scores[security]
        if security == CASH_SECURITY:
            return {
                "selected": security,
                "selected_rank": rank,
                "excluded": excluded,
                "absolute_pass": long_score > 0.0,
                "recent_score": recent_score,
                "recent_pass": recent_score > 0.0,
                "decision": "cash_ranked_factor",
                "target": {security: 1.0},
            }
        if long_score > 0.0:
            return {
                "selected": security,
                "selected_rank": rank,
                "excluded": excluded,
                "absolute_pass": True,
                "recent_score": recent_score,
                "recent_pass": recent_score > 0.0,
                "decision": "ranked_factor_pass",
                "target": {security: 1.0},
            }
        excluded.append(security)

    return {
        "selected": None,
        "selected_rank": None,
        "excluded": excluded,
        "absolute_pass": False,
        "recent_score": None,
        "recent_pass": None,
        "decision": "cash_unavailable",
        "target": {},
    }


# ========================= 独立交易日周期 =========================

def _build_cycle_dates(interval):
    """以TRAIN_START为锚点生成固定的A股交易日周期。"""
    if not isinstance(interval, int) or interval < 1:
        raise ValueError("cycle interval must be a positive integer")
    trade_days = get_trade_days(
        start_date=TRAIN_START,
        end_date=TRAIN_END,
    )
    dates = []
    for index, value in enumerate(trade_days):
        day = value.date() if hasattr(value, "date") else value
        if day < TRAIN_END and index % interval == 0:
            dates.append(day)
    return set(dates)


def _refresh_pool_cache(refresh_date):
    """按独立池刷新周期重建ETF池，并缓存到下一次刷新日。"""
    pool_state = _build_dynamic_etf_pool(refresh_date)
    pool_state["refresh_date"] = refresh_date
    g.pool_cache = pool_state
    g.pool_cache_date = refresh_date
    diagnostics = pool_state["diagnostics"]
    log.info(
        "S04_POOL_REFRESH date=%s liquidity_mode=%s threshold=%.2f "
        "risk_pool=%d cash_available=%s issues=%s"
        % (
            refresh_date,
            diagnostics["liquidity_mode"],
            diagnostics["liquidity_threshold"],
            diagnostics["risk_pool_count"],
            pool_state["cash_available"],
            diagnostics["issues"],
        )
    )
    log.info(
        "S04_POOL_CATEGORY_CONFIG order=%s min_representatives=%s"
        % (ETF_CATEGORY_ORDER, CATEGORY_MIN_REPRESENTATIVES)
    )
    return pool_state


def _get_pool_cache(signal_date):
    """返回信号日可用的最近一次池子；缺失时补建一次。"""
    refresh_dates = [
        date for date in g.pool_refresh_dates if date <= signal_date
    ]
    refresh_date = max(refresh_dates) if refresh_dates else signal_date
    if (
        g.pool_cache is not None
        and g.pool_cache_date is not None
        and g.pool_cache_date >= refresh_date
    ):
        return g.pool_cache
    return _refresh_pool_cache(refresh_date)


# =========================== 动态ETF池构建 ===========================

def _build_dynamic_etf_pool(signal_date):
    """按历史时点、类别覆盖、流动性和Pearson/Spearman组合相关性构建候选池。"""
    metadata, metadata_diagnostics = _collect_point_in_time_metadata(signal_date)
    listing_cutoff = _listing_cutoff(signal_date)
    exclusion_counts = {}
    exclusion_samples = {}
    exclusion_reasons = {}
    category_by_security = {
        security: _classify_etf_category(security, item)
        for security, item in metadata.items()
        if security == CASH_SECURITY or (len(item) >= 4 and item[3])
    }

    metadata_candidates = []
    for security in sorted(metadata):
        reason = _metadata_exclusion_reason(
            security,
            metadata[security],
            signal_date,
            listing_cutoff,
        )
        if reason is None:
            metadata_candidates.append(security)
        else:
            _increment_reason(exclusion_counts, reason)
            exclusion_reasons[security] = reason
            _append_exclusion_sample(
                exclusion_samples,
                reason,
                security,
                metadata[security],
            )

    required_days = _py_max(
        LOOKBACK + 1,
        CORRELATION_DAYS + 1,
        RECENT_LOOKBACK + 1,
        LIQUIDITY_DAYS,
    )
    panels, price_query_failures = _fetch_dynamic_history(
        metadata_candidates,
        signal_date,
        required_days,
    )

    market_candidates = []
    liquidity_metrics = {}
    for security in metadata_candidates:
        reason, metrics = _market_data_quality(
            security,
            panels,
            required_days,
        )
        if reason is None:
            market_candidates.append(security)
            liquidity_metrics[security] = metrics
        else:
            _increment_reason(exclusion_counts, reason)
            exclusion_reasons[security] = reason
            _append_exclusion_sample(
                exclusion_samples,
                reason,
                security,
                metadata[security],
            )

    liquidity_config = _liquidity_thresholds(
        market_candidates,
        liquidity_metrics,
        category_by_security,
    )
    liquidity_metric_key = liquidity_config["metric_key"]
    liquidity_threshold_by_security = {}
    liquid = []
    avg_money = {}
    for security in market_candidates:
        category = category_by_security[security]
        metric = liquidity_metrics[security][liquidity_metric_key]
        security_threshold = liquidity_config["thresholds_by_category"][category]
        liquidity_threshold_by_security[security] = security_threshold
        if metric < security_threshold:
            _increment_reason(exclusion_counts, "low_liquidity")
            exclusion_reasons[security] = "low_liquidity"
            _append_exclusion_sample(
                exclusion_samples,
                "low_liquidity",
                security,
                metadata[security],
            )
            continue
        liquid.append(security)
        avg_money[security] = metric

    # 货币ETF不参与风险相关性去重，只作为防守目的地保留。
    cash_available = CASH_SECURITY in liquid
    risk_liquid_all = [
        security for security in liquid if security != CASH_SECURITY
    ]
    risk_liquid_all.sort(key=lambda security: (-avg_money[security], security))
    uncapped_risk_count = len(risk_liquid_all)
    risk_liquid, liquidity_cap_excluded = _category_aware_liquidity_cap(
        risk_liquid_all,
        category_by_security,
        avg_money,
    )
    for security in liquidity_cap_excluded:
        exclusion_reasons[security] = "outside_liquidity_top_n"
    if liquidity_cap_excluded:
        exclusion_counts["outside_liquidity_top_n"] = len(
            liquidity_cap_excluded
        )

    close_panel = panels["close"]
    returns = close_panel[risk_liquid].pct_change() if risk_liquid else pd.DataFrame()
    risk_pool = []
    duplicates = []
    category_representatives = {}
    pool_limit_count = 0

    # 先为每个有合格标的的类别预留流动性最高的一只。
    for category in RISK_CATEGORY_ORDER:
        category_candidates = [
            security for security in risk_liquid
            if category_by_security.get(security) == category
        ]
        if not category_candidates:
            continue
        representative = category_candidates[0]
        if len(risk_pool) >= MAX_DYNAMIC_RISK_POOL_SIZE:
            pool_limit_count += 1
            exclusion_reasons[representative] = "outside_pool_size_limit"
            continue
        risk_pool.append(representative)
        category_representatives[category] = representative

    # 再用全局流动性顺序填充剩余席位；不会删除已预留类别代表。
    for security in risk_liquid:
        if security in risk_pool:
            continue
        if len(risk_pool) >= MAX_DYNAMIC_RISK_POOL_SIZE:
            pool_limit_count += 1
            exclusion_reasons[security] = "outside_pool_size_limit"
            continue
        duplicate_detail = None
        for representative in risk_pool:
            correlation, lag, pearson, spearman = _max_lead_lag_correlation(
                returns[security],
                returns[representative],
            )
            if correlation >= MAX_DUPLICATE_CORRELATION:
                duplicate_detail = {
                    "security": security,
                    "representative": representative,
                    "correlation": correlation,
                    "pearson": pearson,
                    "spearman": spearman,
                    "lag": lag,
                }
                break
        if duplicate_detail is None:
            risk_pool.append(security)
        else:
            duplicates.append(duplicate_detail)
            _increment_reason(exclusion_counts, "high_correlation_duplicate")
            exclusion_reasons[security] = "high_correlation_duplicate"

    if pool_limit_count:
        exclusion_counts["outside_pool_size_limit"] = pool_limit_count
    pool = list(risk_pool)
    if cash_available:
        pool.append(CASH_SECURITY)
        category_representatives["cash"] = CASH_SECURITY

    category_metadata_counts = _category_counts(metadata_candidates, category_by_security)
    category_quality_counts = _category_counts(market_candidates, category_by_security)
    category_liquid_counts = _category_counts(liquid, category_by_security)
    category_pool_counts = _category_counts(pool, category_by_security)
    available_categories = [
        category for category in ETF_CATEGORY_ORDER
        if category_liquid_counts[category] > 0
    ]
    covered_categories = [
        category for category in available_categories
        if category_pool_counts[category] >= CATEGORY_MIN_REPRESENTATIVES[category]
    ]

    close_values = {
        security: [
            float(value)
            for value in close_panel[security].iloc[-(LOOKBACK + 1):].tolist()
        ]
        for security in pool
    }
    diagnostics = {
        "raw_count": len(metadata),
        "metadata_count": len(metadata_candidates),
        "metadata_pass_count": len(metadata_candidates),
        "market_quality_pass_count": len(market_candidates),
        "liquid_count": len(liquid),
        "liquid_pass_count": len(liquid),
        "liquid_capped_count": len(risk_liquid) + int(cash_available),
        "uncapped_risk_count": uncapped_risk_count,
        "risk_pool_count": len(risk_pool),
        "exclusion_counts": exclusion_counts,
        "exclusion_samples": exclusion_samples,
        "warmup": listing_cutoff is None,
        "metadata_query_failures": metadata_diagnostics["failures"],
        "metadata_query_warnings": metadata_diagnostics["warnings"],
        "metadata_query_counts": metadata_diagnostics["counts"],
        "recognized_etf_count": _py_sum(
            1 for item in metadata.values() if len(item) >= 4 and item[3]
        ),
        "price_query_failures": price_query_failures,
        "liquidity_mode": liquidity_config["mode"],
        "liquidity_metric": liquidity_metric_key,
        "liquidity_threshold": liquidity_config["threshold"],
        "liquidity_threshold_by_security": liquidity_threshold_by_security,
        "liquidity_quantile_threshold": liquidity_config["quantile_threshold"],
        "liquidity_capital_floor": liquidity_config["capital_floor"],
        "liquidity_active_days_min": liquidity_config["active_days_min"],
        "liquidity_thresholds_by_category": liquidity_config["thresholds_by_category"],
        "liquidity_quantiles_by_category": liquidity_config["quantile_thresholds_by_category"],
        "category_metadata_counts": category_metadata_counts,
        "category_quality_counts": category_quality_counts,
        "category_liquid_counts": category_liquid_counts,
        "category_pool_counts": category_pool_counts,
        "category_available_count": len(available_categories),
        "category_covered_count": len(covered_categories),
        "category_coverage_ratio": (
            float(len(covered_categories)) / len(available_categories)
            if available_categories else 1.0
        ),
        "category_available": available_categories,
        "category_covered": covered_categories,
        "category_unavailable": [
            category for category in ETF_CATEGORY_ORDER
            if category_liquid_counts[category] == 0
        ],
        "issues": [],
    }
    result = {
        "pool": pool,
        "risk_pool": risk_pool,
        "cash_available": cash_available,
        "metadata": metadata,
        "close_values": close_values,
        "avg_money": avg_money,
        "liquidity_metrics": liquidity_metrics,
        "liquidity_threshold_by_security": liquidity_threshold_by_security,
        "category_by_security": category_by_security,
        "category_representatives": category_representatives,
        "exclusion_reasons": exclusion_reasons,
        "market_candidates": market_candidates,
        "liquid": liquid,
        "duplicates": duplicates,
        "diagnostics": diagnostics,
    }
    diagnostics["issues"] = _check_pool_invariants(result)
    return result


def _category_counts(securities, category_by_security):
    counts = {}
    for category in ETF_CATEGORY_ORDER:
        counts[category] = _py_sum(
            1
            for security in securities
            if category_by_security.get(security) == category
        )
    return counts


def _category_aware_liquidity_cap(securities, category_by_security, liquidity):
    """保留每个有合格标的类别的第一名，再用流动性填充全局候选上限。"""
    if MAX_LIQUID_CANDIDATES < len(RISK_CATEGORY_ORDER):
        raise ValueError("MAX_LIQUID_CANDIDATES is smaller than category count")
    reserved = []
    for category in RISK_CATEGORY_ORDER:
        candidates = [
            security for security in securities
            if category_by_security.get(security) == category
        ]
        if candidates:
            reserved.append(candidates[0])
    selected = set(reserved)
    for security in securities:
        if len(selected) >= MAX_LIQUID_CANDIDATES:
            break
        selected.add(security)
    excluded = [security for security in securities if security not in selected]
    capped = sorted(
        selected,
        key=lambda security: (-liquidity[security], security),
    )
    return capped, excluded


def _classify_etf_category(security, metadata):
    """使用信号日名称和交易代码做点时分类；未命中的权益ETF归入行业主题。"""
    name = str(metadata[2] if len(metadata) >= 3 else "")
    upper_name = name.upper()
    upper_security = str(security).upper()
    if security == CASH_SECURITY or _py_any(
        keyword in name for keyword in CASH_NAME_KEYWORDS
    ):
        return "cash"
    if security in BROAD_EQUITY_SECURITY_OVERRIDES:
        return "broad_equity"
    if _py_any(
        keyword in name
        for keyword in (
            "国债", "地方债", "政金债", "国开", "债券", "利率债",
            "信用债", "可转债", "城投债", "短融", "债",
        )
    ):
        return "bond"
    if _py_any(
        keyword in name
        for keyword in (
            "黄金", "商品ETF", "商品", "白银", "豆粕", "能源化工",
            "原油", "有色金属期货",
        )
    ):
        return "commodity"
    if upper_security.startswith("513") or _py_any(
        keyword in upper_name
        for keyword in (
            "纳指", "纳斯达克", "标普", "恒生", "港股", "中概", "日经",
            "德国", "DAX", "法国", "印度", "海外", "全球", "东南亚",
            "亚太", "美国", "日本", "英国", "沙特", "越南", "道琼斯",
        )
    ):
        return "cross_border_equity"
    if _py_any(
        keyword in name for keyword in ("红利", "股息", "低波", "高股息")
    ):
        return "dividend_style"
    if _py_any(
        keyword in name
        for keyword in (
            "沪深300", "中证300", "中证500", "中证1000", "中证2000",
            "中证A50", "中证A500", "上证50", "上证180", "上证指数",
            "深证成指", "中小", "创业板ETF", "创业板50", "科创50",
            "科创100", "科创200", "双创", "国证2000", "国证1000",
            "国证A指", "宽基", "大盘", "小盘", "中盘",
        )
    ):
        return "broad_equity"
    return "industry_theme"


def _increment_reason(reasons, reason):
    reasons[reason] = reasons.get(reason, 0) + 1


def _append_exclusion_sample(samples, reason, security, metadata):
    items = samples.setdefault(reason, [])
    if len(items) >= 3:
        return
    items.append(
        "%s|query_type=%s|row_type=%s|name=%s"
        % (security, metadata[0], _security_row_type(metadata[1]), metadata[2])
    )


def _collect_point_in_time_metadata(signal_date):
    """查询历史名单；ETF查询优先，fund仅作兼容补充和货币基金来源。"""
    metadata = {}
    query_failures = []
    query_warnings = []
    query_counts = {"etf_pool": 0, "fund": 0}
    query_specs = (
        ("etf_pool", ETF_QUERY_TYPES),
        ("fund", ["fund"]),
    )
    for query_type, query_types in query_specs:
        try:
            table = get_all_securities(query_types, date=signal_date)
        except Exception as error:
            query_failures.append(
                "%s:%s" % (query_type, type(error).__name__)
            )
            log.warn(
                "S04_POOL_METADATA_FAIL date=%s type=%s error=%s"
                % (signal_date, query_type, error)
            )
            continue
        if table is None or len(table) == 0:
            query_warnings.append("%s:empty" % query_type)
            log.warn(
                "S04_POOL_METADATA_EMPTY date=%s type=%s"
                % (signal_date, query_type)
            )
            continue
        query_counts[query_type] = len(table)
        for security, row in table.iterrows():
            name = _security_name(row)
            if security not in metadata:
                metadata[security] = (
                    query_type,
                    row,
                    name,
                    _is_etf_metadata(query_type, row, name),
                )
    return metadata, {
        "failures": query_failures,
        "warnings": query_warnings,
        "counts": query_counts,
    }


def _security_name(row):
    for field in ("display_name", "name"):
        if field in row.index and pd.notnull(row[field]):
            return str(row[field])
    return ""


def _security_row_type(row):
    """读取聚宽元数据中的基金细分类；不同数据版本可能没有该字段。"""
    if "type" not in row.index or pd.isnull(row["type"]):
        return ""
    return str(row["type"])


def _is_etf_metadata(query_type, row, name):
    """判断风险标的是ETF；优先使用查询来源和行类型，名称只作兼容回退。"""
    if query_type == "etf_pool":
        return True

    row_type = _security_row_type(row).strip().lower()
    if row_type in ("etf", "fund_etf", "etf_fund"):
        return True

    upper_name = name.upper()
    return "ETF" in upper_name or "交易型开放式" in name


def _listing_cutoff(signal_date):
    """返回上市满ELIGIBILITY_DAYS交易日所需的最晚上市日期。"""
    trade_days = get_trade_days(
        end_date=signal_date,
        count=ELIGIBILITY_DAYS,
    )
    if len(trade_days) < ELIGIBILITY_DAYS:
        return None
    cutoff = trade_days[0]
    return cutoff.date() if hasattr(cutoff, "date") else cutoff


def _metadata_exclusion_reason(
    security,
    metadata,
    signal_date,
    listing_cutoff,
):
    """返回元数据层的排除原因；None表示通过。"""
    query_type, row, name, is_etf = metadata
    upper_name = name.upper()
    row_type = _security_row_type(row).strip().lower()

    if security != CASH_SECURITY and not is_etf:
        return "non_etf_fund"
    if row_type in ("lof", "fja", "fjb", "分级基金a", "分级基金b"):
        return "excluded_product_type"
    if _py_any(keyword.upper() in upper_name for keyword in EXCLUDED_NAME_KEYWORDS):
        return "excluded_product_type"
    if (
        security != CASH_SECURITY
        and _py_any(keyword in name for keyword in CASH_NAME_KEYWORDS)
    ):
        return "cash_like_duplicate"

    start_date = _row_date(row, "start_date")
    end_date = _row_date(row, "end_date")
    if start_date is None or end_date is None:
        return "missing_lifecycle"
    if end_date < signal_date:
        return "ended"
    if listing_cutoff is None or start_date > listing_cutoff:
        return "too_new"
    return None


def _row_date(row, field):
    if field not in row.index or pd.isnull(row[field]):
        return None
    value = row[field]
    return value.date() if hasattr(value, "date") else value


def _fetch_dynamic_history(securities, end_date, count):
    """分批获取全市场历史数据，避免逐只ETF调用造成聚宽回测超时。"""
    frames = []
    query_failures = []
    for start in range(0, len(securities), DYNAMIC_DATA_CHUNK_SIZE):
        chunk = securities[start:start + DYNAMIC_DATA_CHUNK_SIZE]
        try:
            frame = get_price(
                chunk,
                end_date=end_date,
                count=count,
                frequency="1d",
                fields=DATA_FIELDS,
                fq="pre",
                panel=False,
            )
        except Exception as error:
            log.warn(
                "S04_POOL_PRICE_FAIL date=%s chunk_start=%d size=%d error=%s"
                % (end_date, start, len(chunk), error)
            )
            query_failures.append(
                "start=%d,size=%d,%s" % (start, len(chunk), type(error).__name__)
            )
            continue
        normalized = _normalize_dynamic_price_frame(frame, chunk)
        if normalized is not None and len(normalized):
            frames.append(normalized)
        else:
            query_failures.append(
                "start=%d,size=%d,invalid_response" % (start, len(chunk))
            )

    if not frames:
        return {field: pd.DataFrame() for field in DATA_FIELDS}, query_failures

    long_frame = pd.concat(frames, ignore_index=True)
    panels = {
        field: long_frame.pivot_table(
            index="time",
            columns="code",
            values=field,
            aggfunc="last",
        ).sort_index()
        for field in DATA_FIELDS
    }
    return panels, query_failures


def _normalize_dynamic_price_frame(frame, securities):
    if frame is None or len(frame) == 0:
        return None
    result = frame.copy()
    if "time" not in result.columns:
        result = result.reset_index()
        if "time" not in result.columns:
            result = result.rename(columns={result.columns[0]: "time"})
    if "code" not in result.columns:
        for code_column in ("security", "security_code", "stock_code"):
            if code_column in result.columns:
                result = result.rename(columns={code_column: "code"})
                break
    if "code" not in result.columns:
        if len(securities) != 1:
            return None
        result["code"] = securities[0]
    required = ["time", "code"] + DATA_FIELDS
    if _py_any(column not in result.columns for column in required):
        return None
    return result[required]


def _fetch_scoring_close_values(securities, end_date):
    """池成员固定期间，每个调仓日仍用当日收盘价重新计算因子。"""
    if not securities:
        return {}, {}

    frames = []
    failures = {}
    for start in range(0, len(securities), DYNAMIC_DATA_CHUNK_SIZE):
        chunk = securities[start:start + DYNAMIC_DATA_CHUNK_SIZE]
        try:
            frame = get_price(
                chunk,
                end_date=end_date,
                count=LOOKBACK + 1,
                frequency="1d",
                fields=["close"],
                fq="pre",
                panel=False,
            )
        except Exception as error:
            for security in chunk:
                failures[security] = "price_query=%s" % type(error).__name__
            continue

        normalized = _normalize_close_frame(frame, chunk)
        if normalized is None or len(normalized) == 0:
            for security in chunk:
                failures[security] = "invalid_price_response"
            continue
        frames.append(normalized)

    if not frames:
        return {}, failures

    long_frame = pd.concat(frames, ignore_index=True)
    close_panel = long_frame.pivot_table(
        index="time",
        columns="code",
        values="close",
        aggfunc="last",
    ).sort_index()
    close_values = {}
    for security in securities:
        if security not in close_panel:
            failures[security] = "missing_close_column"
            continue
        values = close_panel[security].iloc[-(LOOKBACK + 1):]
        if len(values) != LOOKBACK + 1 or values.isnull().any():
            failures[security] = "incomplete_close_history"
            continue
        converted = [float(value) for value in values.tolist()]
        if _py_any(
            not math.isfinite(value) or value <= 0 for value in converted
        ):
            failures[security] = "invalid_close_history"
            continue
        close_values[security] = converted
    return close_values, failures


def _normalize_close_frame(frame, securities):
    if frame is None or len(frame) == 0:
        return None
    result = frame.copy()
    if "time" not in result.columns:
        result = result.reset_index()
        if "time" not in result.columns:
            result = result.rename(columns={result.columns[0]: "time"})
    if "code" not in result.columns:
        for code_column in ("security", "security_code", "stock_code"):
            if code_column in result.columns:
                result = result.rename(columns={code_column: "code"})
                break
    if "code" not in result.columns:
        if len(securities) != 1:
            return None
        result["code"] = securities[0]
    required = ["time", "code", "close"]
    if _py_any(column not in result.columns for column in required):
        return None
    return result[required]


def _market_data_quality(security, panels, required_days):
    """检查行情质量并返回流动性统计；金额门槛在类别横截面汇总后统一计算。"""
    if _py_any(
        field not in panels or security not in panels[field]
        for field in DATA_FIELDS
    ):
        return "missing_market_columns", None

    close_tail = panels["close"][security].iloc[-required_days:]
    if len(close_tail) != required_days or close_tail.isnull().sum() > 0:
        return "incomplete_price_history", None
    if _py_any(
        not math.isfinite(float(value)) or float(value) <= 0
        for value in close_tail.tolist()
    ):
        return "invalid_price_history", None

    recent = pd.DataFrame(
        {
            field: panels[field][security].iloc[-LIQUIDITY_DAYS:]
            for field in DATA_FIELDS
        }
    )
    recent = recent.apply(pd.to_numeric, errors="coerce")
    liquidity_valid = recent.notnull().all(axis=1)
    liquidity_valid &= recent["volume"] > 0
    if LIQUIDITY_MODE == "L3":
        liquidity_valid &= recent["money"] >= 0
        for field in ("open", "high", "low", "close"):
            liquidity_valid &= recent[field] > 0

    valid_days = int(liquidity_valid.sum())
    active_days_min = (
        LIQUIDITY_DAYS
        if LIQUIDITY_MODE == "L0"
        else int(math.ceil(LIQUIDITY_DAYS * MIN_ACTIVE_DAYS_RATIO))
    )
    if valid_days < active_days_min:
        return "incomplete_60d_fields", None

    money_values = recent.loc[liquidity_valid, "money"]
    mean_money = float(money_values.mean())
    median_money = float(money_values.median())
    if not math.isfinite(mean_money) or not math.isfinite(median_money):
        return "invalid_liquidity_history", None
    return None, {
        "mean_money": mean_money,
        "median_money": median_money,
        "valid_days": valid_days,
        "active_days_ratio": float(valid_days) / LIQUIDITY_DAYS,
    }


def _liquidity_thresholds(securities, metrics, category_by_security):
    """返回L0或L3的流动性阈值和审计参数。"""
    if LIQUIDITY_MODE == "L0":
        return {
            "mode": "L0",
            "metric_key": "mean_money",
            "threshold": MIN_AVG_MONEY,
            "quantile_threshold": MIN_AVG_MONEY,
            "capital_floor": MIN_AVG_MONEY,
            "active_days_min": LIQUIDITY_DAYS,
            "thresholds_by_category": {
                category: MIN_AVG_MONEY for category in ETF_CATEGORY_ORDER
            },
            "quantile_thresholds_by_category": {
                category: MIN_AVG_MONEY for category in ETF_CATEGORY_ORDER
            },
        }

    if MAX_PARTICIPATION <= 0 or LIQUIDITY_CAPITAL_LEVERAGE <= 0:
        raise ValueError("L3 liquidity capacity parameters must be positive")
    capital_floor = (
        INITIAL_CAPITAL
        * LIQUIDITY_CAPITAL_LEVERAGE
        / MAX_PARTICIPATION
        * LIQUIDITY_BUFFER
    )
    hard_floor = _py_max(ABSOLUTE_LIQUIDITY_FLOOR, capital_floor)
    category_values = {
        category: [
            metrics[security]["median_money"]
            for security in securities
            if category_by_security.get(security) == category
        ]
        for category in ETF_CATEGORY_ORDER
    }
    quantile_thresholds = {
        category: (
            float(pd.Series(values).quantile(LIQUIDITY_QUANTILE))
            if values else 0.0
        )
        for category, values in category_values.items()
    }
    thresholds = {
        category: _py_max(hard_floor, quantile_thresholds[category])
        for category in ETF_CATEGORY_ORDER
    }
    values = [metrics[security]["median_money"] for security in securities]
    global_quantile = (
        float(pd.Series(values).quantile(LIQUIDITY_QUANTILE))
        if values else 0.0
    )
    return {
        "mode": "L3",
        "metric_key": "median_money",
        "threshold": hard_floor,
        "quantile_threshold": global_quantile,
        "capital_floor": capital_floor,
        "active_days_min": int(math.ceil(LIQUIDITY_DAYS * MIN_ACTIVE_DAYS_RATIO)),
        "thresholds_by_category": thresholds,
        "quantile_thresholds_by_category": quantile_thresholds,
    }


def _max_lead_lag_correlation(left, right):
    """返回时间错位中的保守Pearson/Spearman组合相关性及明细。"""
    best = MIN_DUPLICATE_CORRELATION
    best_lag = None
    best_pearson = MIN_DUPLICATE_CORRELATION
    best_spearman = MIN_DUPLICATE_CORRELATION
    # Prefer same-day alignment when tied; lead/lag checks remain a fallback.
    for lag in (0, -1, 1):
        pair = pd.concat([left, right.shift(lag)], axis=1).dropna()
        if len(pair) < MIN_CORRELATION_OBSERVATIONS:
            continue
        pearson = float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method="pearson"))
        spearman = float(pair.iloc[:, 0].corr(pair.iloc[:, 1], method="spearman"))
        positive_scores = [
            score for score in (pearson, spearman)
            if math.isfinite(score) and score > MIN_DUPLICATE_CORRELATION
        ]
        combined = _py_max(positive_scores) if positive_scores else MIN_DUPLICATE_CORRELATION
        if combined > best:
            best = combined
            best_lag = lag
            best_pearson = pearson if math.isfinite(pearson) else MIN_DUPLICATE_CORRELATION
            best_spearman = spearman if math.isfinite(spearman) else MIN_DUPLICATE_CORRELATION
    return best, best_lag, best_pearson, best_spearman


def _check_pool_invariants(result):
    issues = []
    risk_pool = result["risk_pool"]
    pool = result["pool"]
    diagnostics = result["diagnostics"]
    liquid_count = diagnostics["liquid_pass_count"]
    market_candidates = result["market_candidates"]
    liquid = result["liquid"]
    metrics = result["liquidity_metrics"]
    threshold_by_security = result["liquidity_threshold_by_security"]
    category_by_security = result["category_by_security"]
    category_liquid_counts = diagnostics["category_liquid_counts"]
    category_pool_counts = diagnostics["category_pool_counts"]

    expected_metric = (
        "mean_money" if LIQUIDITY_MODE == "L0" else "median_money"
    )
    expected_active_days = (
        LIQUIDITY_DAYS
        if LIQUIDITY_MODE == "L0"
        else int(math.ceil(LIQUIDITY_DAYS * MIN_ACTIVE_DAYS_RATIO))
    )
    if diagnostics["liquidity_mode"] != LIQUIDITY_MODE:
        issues.append("liquidity_mode_mismatch")
    if diagnostics["liquidity_metric"] != expected_metric:
        issues.append("liquidity_metric_mismatch")
    if diagnostics["liquidity_active_days_min"] != expected_active_days:
        issues.append("liquidity_active_days_mismatch")
    if not math.isfinite(diagnostics["liquidity_threshold"]):
        issues.append("liquidity_threshold_not_finite")
    if market_candidates and len(metrics) != len(market_candidates):
        issues.append("liquidity_metric_count_mismatch")
    if len(threshold_by_security) != len(market_candidates):
        issues.append("liquidity_threshold_count_mismatch")
    if liquid_count != len(liquid):
        issues.append("liquid_count_mismatch")

    expected_liquid = []
    for security in market_candidates:
        item = metrics.get(security)
        if item is None:
            issues.append("missing_liquidity_metric")
            continue
        if item["valid_days"] < expected_active_days:
            issues.append("liquidity_active_days_violation")
        if item[expected_metric] >= threshold_by_security.get(
            security,
            diagnostics["liquidity_threshold"],
        ):
            expected_liquid.append(security)
    if set(expected_liquid) != set(liquid):
        issues.append("liquidity_filter_mismatch")
    for security in liquid:
        item = metrics.get(security)
        if item is None or item[expected_metric] < threshold_by_security.get(
            security,
            diagnostics["liquidity_threshold"],
        ):
            issues.append("liquid_below_threshold")
            break

    if not 0.0 <= diagnostics["category_coverage_ratio"] <= 1.0:
        issues.append("category_coverage_ratio_invalid")
    if diagnostics["category_available_count"] != _py_sum(
        1 for category in ETF_CATEGORY_ORDER
        if category_liquid_counts[category] > 0
    ):
        issues.append("category_available_count_mismatch")
    if diagnostics["category_covered_count"] != _py_sum(
        1 for category in ETF_CATEGORY_ORDER
        if category_pool_counts[category] >= CATEGORY_MIN_REPRESENTATIVES[category]
    ):
        issues.append("category_covered_count_mismatch")
    for category in ETF_CATEGORY_ORDER:
        if category_liquid_counts[category] > 0 and (
            category_pool_counts[category]
            < CATEGORY_MIN_REPRESENTATIVES[category]
        ):
            issues.append("category_coverage_missing:%s" % category)
    for security in pool:
        if security not in category_by_security:
            issues.append("pool_category_missing")
            break

    if len(risk_pool) > MAX_DYNAMIC_RISK_POOL_SIZE:
        issues.append("risk_pool_over_max")
    if not diagnostics["warmup"] and len(risk_pool) < MIN_DYNAMIC_RISK_ASSETS:
        issues.append("risk_pool_below_min")
    if result["cash_available"] and CASH_SECURITY not in pool:
        issues.append("cash_missing_from_pool")
    if not diagnostics["warmup"] and not result["cash_available"]:
        issues.append("cash_unavailable")
    if len(pool) != len(set(pool)):
        issues.append("duplicate_pool_member")
    expected_pool_size = len(risk_pool) + int(result["cash_available"])
    if len(pool) != expected_pool_size:
        issues.append("pool_composition_mismatch")
    if liquid_count < len(risk_pool):
        issues.append("pool_larger_than_liquid_set")
    if len(result["duplicates"]) != diagnostics["exclusion_counts"].get(
        "high_correlation_duplicate", 0
    ):
        issues.append("duplicate_audit_count_mismatch")
    if diagnostics["metadata_query_failures"]:
        issues.append("metadata_query_failed")
    if diagnostics["price_query_failures"]:
        issues.append("price_query_failed")
    return issues


# ========================= 动态池内因子评分 =========================

def _eligible_universe(signal_date):
    """读取独立刷新周期的池子，并用信号日行情重新计算池内因子。"""
    pool_state = _get_pool_cache(signal_date)
    dynamic_pool = pool_state["pool"]
    metadata = pool_state["metadata"]
    diagnostics = pool_state["diagnostics"]

    # 该日志用于区分“构池排除”和“因子计算失败”，便于聚宽回测时审计。
    g.last_pool_diagnostics = diagnostics
    g.last_pool_names = {
        security: metadata[security][2]
        for security in dynamic_pool
        if security in metadata and len(metadata[security]) >= 3
    }
    log.info(
        "S04_POOL_METADATA_COUNTS date=%s etf_pool=%d fund=%d merged=%d recognized_etf=%d"
        % (
            signal_date,
            diagnostics["metadata_query_counts"].get("etf_pool", 0),
            diagnostics["metadata_query_counts"].get("fund", 0),
            diagnostics["raw_count"],
            diagnostics["recognized_etf_count"],
        )
    )
    log.info(
        "S04_POOL date=%s pool_date=%s liquidity_mode=%s threshold=%.2f "
        "raw=%d metadata=%d liquid=%d liquid_capped=%d risk_pool=%d "
        "cash_available=%s category_available=%d category_covered=%d "
        "category_coverage=%.4f warmup=%s issues=%s pool=%s exclusions=%s"
        % (
            signal_date,
            pool_state.get("refresh_date", signal_date),
            diagnostics["liquidity_mode"],
            diagnostics["liquidity_threshold"],
            diagnostics["raw_count"],
            diagnostics["metadata_count"],
            diagnostics["liquid_count"],
            diagnostics["liquid_capped_count"],
            diagnostics["risk_pool_count"],
            CASH_SECURITY in dynamic_pool,
            diagnostics["category_available_count"],
            diagnostics["category_covered_count"],
            diagnostics["category_coverage_ratio"],
            diagnostics["warmup"],
            diagnostics["issues"],
            dynamic_pool,
            diagnostics["exclusion_counts"],
        )
    )
    for category in ETF_CATEGORY_ORDER:
        log.info(
            "S04_POOL_CATEGORY date=%s category=%s label=%s metadata=%d "
            "quality=%d liquid=%d selected=%d available=%d covered=%d "
            "representative=%s quantile_threshold=%.2f threshold=%.2f"
            % (
                signal_date,
                category,
                CATEGORY_LABELS[category],
                diagnostics["category_metadata_counts"][category],
                diagnostics["category_quality_counts"][category],
                diagnostics["category_liquid_counts"][category],
                diagnostics["category_pool_counts"][category],
                int(diagnostics["category_liquid_counts"][category] > 0),
                int(
                    diagnostics["category_pool_counts"][category]
                    >= CATEGORY_MIN_REPRESENTATIVES[category]
                ),
                pool_state["category_representatives"].get(category, "NA"),
                diagnostics["liquidity_quantiles_by_category"][category],
                diagnostics["liquidity_thresholds_by_category"][category],
            )
        )
    log.info(
        "S04_POOL_EXCLUDE_SAMPLE date=%s samples=%s warnings=%s "
        "metadata_errors=%s price_errors=%s"
        % (
            signal_date,
            diagnostics["exclusion_samples"],
            diagnostics["metadata_query_warnings"],
            diagnostics["metadata_query_failures"],
            diagnostics["price_query_failures"],
        )
    )
    for rank, security in enumerate(pool_state["risk_pool"], start=1):
        log.info(
            "S04_POOL_MEMBER date=%s rank=%d security=%s name=%s category=%s avg_money=%.2f"
            % (
                signal_date,
                rank,
                security,
                metadata[security][2],
                pool_state["category_by_security"].get(security, "unknown"),
                pool_state["avg_money"].get(security, 0.0),
            )
        )
    if pool_state["cash_available"]:
        cash_metadata = metadata.get(CASH_SECURITY)
        log.info(
            "S04_POOL_CASH date=%s security=%s name=%s category=%s avg_money=%.2f"
            % (
                signal_date,
                CASH_SECURITY,
                cash_metadata[2] if cash_metadata else "NA",
                pool_state["category_by_security"].get(CASH_SECURITY, "cash"),
                pool_state["avg_money"].get(CASH_SECURITY, 0.0),
            )
        )
    for duplicate in pool_state["duplicates"]:
        log.info(
            "S04_POOL_DUPLICATE date=%s security=%s representative=%s "
            "correlation=%.8f pearson=%.8f spearman=%.8f lag=%s"
            % (
                signal_date,
                duplicate["security"],
                duplicate["representative"],
                duplicate["correlation"],
                duplicate["pearson"],
                duplicate["spearman"],
                duplicate["lag"],
            )
        )
    record(
        pool_raw=diagnostics["raw_count"],
        pool_metadata=diagnostics["metadata_count"],
        pool_liquid=diagnostics["liquid_count"],
        pool_risk=diagnostics["risk_pool_count"],
        pool_cash=int(pool_state["cash_available"]),
        pool_category_available=diagnostics["category_available_count"],
        pool_category_covered=diagnostics["category_covered_count"],
        pool_category_coverage=diagnostics["category_coverage_ratio"],
        pool_warmup=int(diagnostics["warmup"]),
        pool_valid=int(not diagnostics["issues"]),
    )

    if diagnostics["issues"]:
        return (
            [], {}, {}, {}, {}, {}, {}, {}, {}, {}, {}
        )

    close_values_by_security, scoring_price_failures = _fetch_scoring_close_values(
        dynamic_pool,
        signal_date,
    )
    if scoring_price_failures:
        log.info(
            "S04_SCORING_PRICE_FAIL date=%s failures=%s"
            % (signal_date, scoring_price_failures)
        )

    eligible = []
    scores = {}
    recent_scores = {}
    slope_scores = {}
    r2_scores = {}
    path_returns = {}
    efficiency_ratios = {}
    bias_trend_slopes = {}
    factor_metadata = {}
    reasons = {}
    avg_money = pool_state["avg_money"]
    current_data = get_current_data()

    for security in dynamic_pool:
        try:
            current = current_data[security]
        except (KeyError, TypeError):
            current = None
        if current is None:
            reasons[security] = "missing_current_data"
            log.info(
                "S04_ELIGIBILITY date=%s security=%s eligible=0 reason=missing_current_data"
                % (signal_date, security)
            )
            continue
        if getattr(current, "paused", False):
            reasons[security] = "paused"
            log.info(
                "S04_ELIGIBILITY date=%s security=%s eligible=0 reason=paused"
                % (signal_date, security)
            )
            continue
        if security not in close_values_by_security:
            reasons[security] = scoring_price_failures.get(
                security,
                "missing_scoring_close",
            )
            log.info(
                "S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s"
                % (signal_date, security, reasons[security])
            )
            continue
        close_values = close_values_by_security[security]

        start_price = close_values[0]
        end_price = close_values[-1]

        score = end_price / start_price - 1.0
        slope = None
        r2 = None
        path_return = None
        efficiency_ratio = None
        bias_trend_slope = None
        if g.mode == "m3_ols_slope":
            try:
                slope, r2, score = _log_ols_slope_score(close_values)
            except (ValueError, OverflowError) as error:
                reasons[security] = "ols_error=%s" % error
                log.info(
                    "S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s"
                    % (signal_date, security, reasons[security])
                )
                continue
        elif g.mode == "m3e_huber_slope":
            try:
                slope, r2, score, iterations, downweighted = _log_huber_slope_score(
                    close_values
                )
                factor_metadata[security] = {
                    "huber_iterations": iterations,
                    "huber_downweighted": downweighted,
                }
            except (ValueError, OverflowError) as error:
                reasons[security] = "huber_error=%s" % error
                log.info(
                    "S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s"
                    % (signal_date, security, reasons[security])
                )
                continue
        elif g.mode == "m3d_wls_slope":
            try:
                slope, r2, score = _log_wls_slope_score(close_values)
            except (ValueError, OverflowError) as error:
                reasons[security] = "wls_error=%s" % error
                log.info(
                    "S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s"
                    % (signal_date, security, reasons[security])
                )
                continue
        elif g.mode in ("m3b_efficiency", "m3g_efficiency_rank"):
            try:
                path_return, efficiency_ratio, score = _log_efficiency_score(close_values)
            except (ValueError, OverflowError) as error:
                reasons[security] = "efficiency_error=%s" % error
                log.info(
                    "S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s"
                    % (signal_date, security, reasons[security])
                )
                continue
        elif g.mode == "m3c_bias_trend":
            try:
                bias_trend_slope = _bias_trend_score(close_values)
                score = bias_trend_slope
            except (ValueError, OverflowError) as error:
                reasons[security] = "bias_trend_error=%s" % error
                log.info(
                    "S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s"
                    % (signal_date, security, reasons[security])
                )
                continue
        elif g.mode == "m3f_equal_rank":
            try:
                slope, r2, huber_score, iterations, downweighted = (
                    _log_huber_slope_score(close_values)
                )
                path_return, efficiency_ratio, efficiency_score = (
                    _log_efficiency_score(close_values)
                )
                bias_trend_slope = _bias_trend_score(close_values)
                score = 0.0
                factor_metadata[security] = {
                    "huber_iterations": iterations,
                    "huber_downweighted": downweighted,
                    "huber_score": huber_score,
                    "efficiency_score": efficiency_score,
                    "bias_score": bias_trend_slope,
                }
            except (ValueError, OverflowError) as error:
                reasons[security] = "fusion_factor_error=%s" % error
                log.info(
                    "S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s"
                    % (signal_date, security, reasons[security])
                )
                continue
        recent_start_price = close_values[-RECENT_LOOKBACK - 1]
        recent_score = end_price / recent_start_price - 1.0
        eligible.append(security)
        scores[security] = score
        recent_scores[security] = recent_score
        if slope is not None:
            slope_scores[security] = slope
            r2_scores[security] = r2
        if path_return is not None:
            path_returns[security] = path_return
            efficiency_ratios[security] = efficiency_ratio
        if bias_trend_slope is not None:
            bias_trend_slopes[security] = bias_trend_slope
    if g.mode == "m3f_equal_rank" and eligible:
        component_scores = {
            factor: {
                security: factor_metadata[security]["%s_score" % factor]
                for security in eligible
            }
            for factor in FUSION_FACTORS
        }
        fused_scores, fusion_ranks = _equal_rank_fusion_scores(component_scores)
        for security in eligible:
            scores[security] = fused_scores[security]
            for factor in FUSION_FACTORS:
                factor_metadata[security]["%s_rank" % factor] = fusion_ranks[security][factor]

    if g.signal_count == 0:
        for security in sorted(eligible):
            log.info(
                "S04_ELIGIBILITY date=%s security=%s eligible=1 query_type=%s avg_money=%.2f "
                "score=%.8f recent_score=%.8f slope=%s r2=%s path_return=%s efficiency_ratio=%s "
                "bias_trend_slope=%s huber_iterations=%s huber_downweighted=%s "
                "huber_score=%s efficiency_score=%s bias_score=%s huber_rank=%s "
                "efficiency_rank=%s bias_rank=%s"
                % (
                    signal_date,
                    security,
                    metadata[security][0],
                    avg_money[security],
                    scores[security],
                    recent_scores[security],
                    "%.10f" % slope_scores[security] if security in slope_scores else "NA",
                    "%.8f" % r2_scores[security] if security in r2_scores else "NA",
                    "%.10f" % path_returns[security] if security in path_returns else "NA",
                    "%.8f" % efficiency_ratios[security] if security in efficiency_ratios else "NA",
                    "%.10f" % bias_trend_slopes[security] if security in bias_trend_slopes else "NA",
                    factor_metadata.get(security, {}).get("huber_iterations", "NA"),
                    factor_metadata.get(security, {}).get("huber_downweighted", "NA"),
                    factor_metadata.get(security, {}).get("huber_score", "NA"),
                    factor_metadata.get(security, {}).get("efficiency_score", "NA"),
                    factor_metadata.get(security, {}).get("bias_score", "NA"),
                    factor_metadata.get(security, {}).get("huber_rank", "NA"),
                    factor_metadata.get(security, {}).get("efficiency_rank", "NA"),
                    factor_metadata.get(security, {}).get("bias_rank", "NA"),
                )
            )

    return (
        sorted(eligible),
        scores,
        recent_scores,
        reasons,
        avg_money,
        slope_scores,
        r2_scores,
        path_returns,
        efficiency_ratios,
        bias_trend_slopes,
        factor_metadata,
    )


# ============================== 因子公式 ==============================

def _equal_rank_fusion_scores(component_scores):
    """Return centered equal-weight Borda scores and per-factor ranks."""
    factor_names = sorted(component_scores)
    if not factor_names:
        raise ValueError("rank fusion requires at least one factor")
    securities = sorted(component_scores[factor_names[0]])
    if not securities:
        raise ValueError("rank fusion requires at least one security")
    security_set = set(securities)
    ranks = {security: {} for security in securities}

    for factor in factor_names:
        values = component_scores[factor]
        if set(values) != security_set:
            raise ValueError("rank fusion factors must cover the same securities")
        invalid_count = sum(
            1 for value in values.values() if not math.isfinite(float(value))
        )
        if invalid_count:
            raise ValueError("rank fusion scores must be finite")
        ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))
        for rank, (security, _) in enumerate(ranked, start=1):
            ranks[security][factor] = rank

    security_count = len(securities)
    if security_count == 1:
        return {securities[0]: 0.0}, ranks
    denominator = float((security_count - 1) * len(factor_names))
    fused_scores = {
        security: sum(
            security_count + 1 - 2 * ranks[security][factor]
            for factor in factor_names
        )
        / denominator
        for security in securities
    }
    return fused_scores, ranks


def _log_ols_slope_score(closes):
    """Return (log-price OLS slope, R2, slope*R2) for a frozen price window."""
    values = [float(value) for value in closes]
    invalid_count = sum(
        1 for value in values if not math.isfinite(value) or value <= 0
    )
    if len(values) < 2 or invalid_count:
        raise ValueError(
            "OLS requires at least 2 finite positive closes; n=%s invalid=%s"
            % (len(values), invalid_count)
        )
    y = [math.log(value) for value in values]
    n = len(y)
    x_mean = (n - 1) / 2.0
    y_mean = sum(y) / n
    denom = sum((index - x_mean) ** 2 for index in range(n))
    slope = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(y)) / denom
    intercept = y_mean - slope * x_mean
    residual = sum((value - (intercept + slope * index)) ** 2 for index, value in enumerate(y))
    total = sum((value - y_mean) ** 2 for value in y)
    r2 = 1.0 - residual / total if total > 0 else 0.0
    r2 = max(0.0, min(1.0, r2))
    return slope, r2, slope * r2


def _log_wls_slope_score(closes):
    """Return log-price WLS slope, weighted R2 and slope*R2."""
    values = [float(value) for value in closes]
    invalid_count = sum(
        1 for value in values if not math.isfinite(value) or value <= 0
    )
    if len(values) < 2 or invalid_count:
        raise ValueError(
            "WLS requires at least 2 finite positive closes; n=%s invalid=%s"
            % (len(values), invalid_count)
        )

    y = [math.log(value) for value in values]
    n = len(y)
    weights = [1.0 + index / float(n - 1) for index in range(n)]
    weight_sum = sum(weights)
    x_mean = sum(weight * index for index, weight in enumerate(weights)) / weight_sum
    y_mean = sum(weight * value for weight, value in zip(weights, y)) / weight_sum
    denominator = sum(
        weight * (index - x_mean) ** 2
        for index, weight in enumerate(weights)
    )
    slope = sum(
        weight * (index - x_mean) * (value - y_mean)
        for index, (weight, value) in enumerate(zip(weights, y))
    ) / denominator
    intercept = y_mean - slope * x_mean
    residual = sum(
        weight * (value - (intercept + slope * index)) ** 2
        for index, (weight, value) in enumerate(zip(weights, y))
    )
    total = sum(
        weight * (value - y_mean) ** 2
        for weight, value in zip(weights, y)
    )
    r2 = 1.0 - residual / total if total > 0 else 0.0
    r2 = max(0.0, min(1.0, r2))
    return slope, r2, slope * r2


def _median(values):
    ordered = sorted(float(value) for value in values)
    n = len(ordered)
    if n == 0:
        raise ValueError("median requires at least one value")
    middle = n // 2
    if n % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _require_finite_outputs(name, **values):
    invalid = {
        key: value
        for key, value in values.items()
        if not math.isfinite(float(value))
    }
    if invalid:
        raise ValueError("%s produced non-finite output: %s" % (name, invalid))


def _weighted_line_fit(y, weights):
    weight_sum = sum(weights)
    if weight_sum <= 0:
        raise ValueError("regression weights must have positive sum")
    x_mean = sum(weight * index for index, weight in enumerate(weights)) / weight_sum
    y_mean = sum(weight * value for weight, value in zip(weights, y)) / weight_sum
    denominator = sum(
        weight * (index - x_mean) ** 2
        for index, weight in enumerate(weights)
    )
    if denominator <= 0:
        raise ValueError("regression denominator must be positive")
    slope = sum(
        weight * (index - x_mean) * (value - y_mean)
        for index, (weight, value) in enumerate(zip(weights, y))
    ) / denominator
    return y_mean - slope * x_mean, slope


def _log_huber_slope_score(
    closes,
    epsilon=HUBER_EPSILON,
    max_iterations=HUBER_MAX_ITERATIONS,
    tolerance=HUBER_TOLERANCE,
):
    """Return Huber IRLS slope, robust weighted R2, score and diagnostics."""
    values = [float(value) for value in closes]
    invalid_count = sum(
        1 for value in values if not math.isfinite(value) or value <= 0
    )
    if len(values) < 2 or invalid_count:
        raise ValueError(
            "Huber requires at least 2 finite positive closes; n=%s invalid=%s"
            % (len(values), invalid_count)
        )
    if epsilon <= 0 or max_iterations <= 0 or tolerance <= 0:
        raise ValueError("Huber parameters must be positive")

    y = [math.log(value) for value in values]
    weights = [1.0] * len(y)
    intercept, slope = _weighted_line_fit(y, weights)
    iterations = 0
    scale_floor = 1e-12

    for iteration in range(1, max_iterations + 1):
        residuals = [
            value - (intercept + slope * index)
            for index, value in enumerate(y)
        ]
        residual_median = _median(residuals)
        mad = _median(abs(residual - residual_median) for residual in residuals)
        scale = mad / 0.6744897501960817
        if scale <= scale_floor:
            break
        threshold = epsilon * scale
        weights = [
            1.0 if abs(residual) <= threshold else threshold / abs(residual)
            for residual in residuals
        ]
        new_intercept, new_slope = _weighted_line_fit(y, weights)
        iterations = iteration
        converged = max(
            abs(new_intercept - intercept), abs(new_slope - slope)
        ) <= tolerance
        intercept, slope = new_intercept, new_slope
        if converged:
            break

    residuals = [
        value - (intercept + slope * index)
        for index, value in enumerate(y)
    ]
    residual_median = _median(residuals)
    mad = _median(abs(residual - residual_median) for residual in residuals)
    scale = mad / 0.6744897501960817
    if scale > scale_floor:
        threshold = epsilon * scale
        weights = [
            1.0 if abs(residual) <= threshold else threshold / abs(residual)
            for residual in residuals
        ]
        intercept, slope = _weighted_line_fit(y, weights)
        residuals = [
            value - (intercept + slope * index)
            for index, value in enumerate(y)
        ]

    weight_sum = sum(weights)
    y_mean = sum(weight * value for weight, value in zip(weights, y)) / weight_sum
    residual = sum(
        weight * error**2 for weight, error in zip(weights, residuals)
    )
    total = sum(
        weight * (value - y_mean) ** 2
        for weight, value in zip(weights, y)
    )
    r2 = 1.0 - residual / total if total > 0 else 0.0
    r2 = max(0.0, min(1.0, r2))
    downweighted = sum(1 for weight in weights if weight < 1.0 - 1e-12)
    score = slope * r2
    _require_finite_outputs("Huber", slope=slope, r2=r2, score=score)
    return slope, r2, score, iterations, downweighted


def _log_efficiency_score(closes):
    """Return (log path return, efficiency ratio, return*efficiency)."""
    values = [float(value) for value in closes]
    invalid_count = sum(
        1 for value in values if not math.isfinite(value) or value <= 0
    )
    if len(values) < 2 or invalid_count:
        raise ValueError(
            "efficiency requires at least 2 finite positive closes; n=%s invalid=%s"
            % (len(values), invalid_count)
        )
    log_prices = [math.log(value) for value in values]
    path_return = log_prices[-1] - log_prices[0]
    path_length = sum(
        abs(log_prices[index] - log_prices[index - 1])
        for index in range(1, len(log_prices))
    )
    efficiency_ratio = abs(path_return) / path_length if path_length > 0 else 0.0
    efficiency_ratio = max(0.0, min(1.0, efficiency_ratio))
    score = path_return * efficiency_ratio
    _require_finite_outputs(
        "efficiency",
        path_return=path_return,
        efficiency_ratio=efficiency_ratio,
        score=score,
    )
    return path_return, efficiency_ratio, score


def _bias_trend_score(closes, ma_window=90, trend_points=25):
    """Return the OLS slope of normalized price/MA90 over the latest 25 points."""
    values = [float(value) for value in closes]
    required = ma_window + trend_points - 1
    invalid_count = sum(
        1 for value in values if not math.isfinite(value) or value <= 0
    )
    if ma_window <= 0 or trend_points < 2 or len(values) < required or invalid_count:
        raise ValueError(
            "bias trend requires %s finite positive closes; n=%s invalid=%s"
            % (required, len(values), invalid_count)
        )

    bias_values = []
    first_index = len(values) - trend_points
    for index in range(first_index, len(values)):
        ma_start = index - ma_window + 1
        moving_average = sum(values[ma_start : index + 1]) / float(ma_window)
        bias_values.append(values[index] / moving_average)

    base_bias = bias_values[0]
    if not math.isfinite(base_bias) or base_bias <= 0:
        raise ValueError("first bias must be finite and positive")
    normalized = [value / base_bias for value in bias_values]
    invalid_count = sum(1 for value in normalized if not math.isfinite(value))
    if invalid_count:
        raise ValueError("bias trend produced non-finite normalized values")
    n = len(normalized)
    x_mean = (n - 1) / 2.0
    y_mean = sum(normalized) / n
    denominator = sum((index - x_mean) ** 2 for index in range(n))
    score = sum(
        (index - x_mean) * (value - y_mean)
        for index, value in enumerate(normalized)
    ) / denominator
    _require_finite_outputs("bias trend", score=score)
    return score


# ============================ T+1交易执行 ============================

def execute_sells(context):
    if not _pending_from_prior_day(context):
        return
    current_data = get_current_data()
    if not _ensure_target_amounts(context, current_data):
        return
    target_amounts = g.pending["target_amounts"]
    for security, position in list(context.portfolio.positions.items()):
        current_amount = int(position.total_amount)
        target_amount = int(target_amounts.get(security, 0))
        if target_amount == 0:
            amount = current_amount
        else:
            amount = ((current_amount - target_amount) // 100) * 100
        if amount <= 0:
            continue
        if not _can_trade(security, "sell", current_data):
            log.info(
                "S04_BLOCK date=%s side=sell security=%s current=%s target=%s"
                % (context.current_dt, security, target_amount, current_amount)
            )
            continue
        if target_amount == 0:
            submitted_order = order_target(security, 0)
        else:
            submitted_order = order(security, -amount)
        log.info(
            "S04_ORDER date=%s signal_date=%s side=sell security=%s current=%s target=%s amount=%s order=%s"
            % (
                context.current_dt,
                g.pending["signal_date"],
                security,
                current_amount,
                target_amount,
                amount,
                submitted_order,
            )
        )


def execute_buys(context):
    if not _pending_from_prior_day(context):
        return
    current_data = get_current_data()
    if not _ensure_target_amounts(context, current_data):
        return
    target_amounts = g.pending["target_amounts"]
    if not _all_positions_at_target(context, allow_underweight=True):
        return

    for security in sorted(target_amounts):
        target_amount = int(target_amounts[security])
        current_amount = (
            int(context.portfolio.positions[security].total_amount)
            if security in context.portfolio.positions
            else 0
        )
        amount = ((target_amount - current_amount) // 100) * 100
        if amount < 100:
            continue
        if not _can_trade(security, "buy", current_data):
            log.info(
                "S04_BLOCK date=%s side=buy security=%s current=%s target=%s"
                % (context.current_dt, security, current_amount, target_amount)
            )
            continue
        buy_amount = min(amount, _affordable_buy_amount(context, security, current_data))
        if buy_amount < 100:
            log.info(
                "S04_TARGET_REVISED date=%s security=%s old_target=%s new_target=%s reason=cash_limit"
                % (context.current_dt, security, target_amount, current_amount)
            )
            target_amounts[security] = current_amount
            continue
        if buy_amount < amount:
            revised_target = current_amount + buy_amount
            log.info(
                "S04_TARGET_REVISED date=%s security=%s old_target=%s new_target=%s reason=cash_limit"
                % (context.current_dt, security, target_amount, revised_target)
            )
            target_amounts[security] = revised_target
        submitted_order = order(security, buy_amount)
        log.info(
            "S04_ORDER date=%s signal_date=%s side=buy security=%s current=%s target=%s amount=%s order=%s"
            % (
                context.current_dt,
                g.pending["signal_date"],
                security,
                current_amount,
                target_amount,
                buy_amount,
                submitted_order,
            )
        )

    if _pending_satisfied(context):
        log.info(
            "S04_EXECUTION_COMPLETE date=%s signal_date=%s attempts=%s target=%s"
            % (
                context.current_dt,
                g.pending["signal_date"],
                g.pending["attempts"],
                g.pending["target"],
            )
        )
        g.pending = None


def _pending_from_prior_day(context):
    if g.pending is None:
        return False
    signal_date = g.pending["signal_date"]
    today = context.current_dt.date()
    if today <= signal_date:
        return False
    if g.pending["last_attempt"] != today:
        if g.pending["attempts"] >= 3:
            return False
        g.pending["attempts"] += 1
        g.pending["last_attempt"] = today
    return True


def _pending_satisfied(context):
    if g.pending is None:
        return True
    target_amounts = g.pending.get("target_amounts")
    if target_amounts is None:
        return False
    for security, position in context.portfolio.positions.items():
        current_amount = int(position.total_amount)
        target_amount = int(target_amounts.get(security, 0))
        if target_amount == 0 and current_amount:
            return False
        if target_amount > 0 and abs(current_amount - target_amount) >= 100:
            return False
    for security, target_amount in target_amounts.items():
        if target_amount > 0:
            current_amount = (
                int(context.portfolio.positions[security].total_amount)
                if security in context.portfolio.positions
                else 0
            )
            if abs(current_amount - int(target_amount)) >= 100:
                return False
    return True


def _all_positions_at_target(context, allow_underweight=False):
    if g.pending is None or g.pending.get("target_amounts") is None:
        return False
    target_amounts = g.pending["target_amounts"]
    for security, position in context.portfolio.positions.items():
        current_amount = int(position.total_amount)
        target_amount = int(target_amounts.get(security, 0))
        if target_amount == 0 and current_amount:
            return False
        if target_amount > 0 and current_amount > target_amount + 99:
            return False
    return True


def _ensure_target_amounts(context, current_data):
    if g.pending is None:
        return False
    if g.pending.get("target_amounts") is not None:
        return True
    total_value = float(context.portfolio.total_value)
    target_amounts = {security: 0 for security in context.portfolio.positions}
    for security, weight in sorted(g.pending["target"].items()):
        current = current_data[security]
        price = getattr(current, "day_open", None) or getattr(current, "last_price", None)
        if price is None or price != price or price <= 0:
            log.info(
                "S04_BLOCK date=%s side=target security=%s reason=missing_execution_price"
                % (context.current_dt, security)
            )
            return False
        budget = total_value * float(weight)
        per_share_cost = float(price) * (1.0 + SLIPPAGE) * (1.0 + COMMISSION)
        shares = int(max(budget - 5.0, 0.0) / per_share_cost / 100) * 100
        target_amounts[security] = max(shares, 0)
    g.pending["target_amounts"] = target_amounts
    log.info(
        "S04_TARGET_AMOUNTS date=%s signal_date=%s target=%s target_amounts=%s"
        % (context.current_dt, g.pending["signal_date"], g.pending["target"], target_amounts)
    )
    return True


def _affordable_buy_amount(context, security, current_data):
    current = current_data[security]
    price = getattr(current, "last_price", None) or getattr(current, "day_open", None)
    if price is None or price != price or price <= 0:
        return 0
    available = max(float(context.portfolio.available_cash) - 5.0, 0.0)
    per_share_cost = float(price) * (1.0 + SLIPPAGE) * (1.0 + COMMISSION)
    return int(available / per_share_cost / 100) * 100


def _expire_unfilled_signal(context):
    if g.pending is None or g.pending["last_attempt"] != context.current_dt.date():
        return
    if _pending_satisfied(context) or g.pending["attempts"] < 3:
        return
    log.info(
        "S04_EXPIRE date=%s signal_date=%s attempts=%s target=%s"
        % (context.current_dt.date(), g.pending["signal_date"], g.pending["attempts"], g.pending["target"])
    )
    g.pending = None


def _can_trade(security, side, current_data):
    current = current_data[security]
    day_open = current.day_open
    if current.paused or day_open is None or day_open != day_open or day_open <= 0:
        return False
    if (
        side == "buy"
        and current.high_limit is not None
        and current.high_limit == current.high_limit
        and day_open >= current.high_limit
    ):
        return False
    if (
        side == "sell"
        and current.low_limit is not None
        and current.low_limit == current.low_limit
        and day_open <= current.low_limit
    ):
        return False
    return True


def _safe_buy_target_value(context, current_value, desired_value):
    """Reserve commission and price-related slippage before a buy order.

    JoinQuant's order_target_value treats the target as position value and
    charges costs on top. Reserving the available cash and minimum commission
    prevents a nominal 100% target from creating negative cash after fills.
    """
    incremental = max(desired_value - current_value, 0.0)
    available_cash = max(float(context.portfolio.available_cash), 0.0)
    cash_after_min_commission = max(available_cash - 5.0, 0.0)
    max_incremental = cash_after_min_commission / (1.0 + COMMISSION + SLIPPAGE)
    return current_value + min(incremental, max_incremental)


# ========================= 标签、订单与账户审计 =========================

def _update_mature_labels(today):
    remaining = []
    matured_count = 0
    trade_day_count_cache = {}
    for label in g.labels:
        signal_date = label["signal_date"]
        if signal_date not in trade_day_count_cache:
            trade_day_count_cache[signal_date] = len(
                get_trade_days(start_date=signal_date, end_date=today)
            )
        if trade_day_count_cache[signal_date] < LABEL_HORIZON + 1:
            remaining.append(label)
            continue
        frame = get_price(
            label["security"],
            end_date=today,
            count=LABEL_HORIZON + 1,
            frequency="1d",
            fields=["close"],
            fq="pre",
        )
        if len(frame) != LABEL_HORIZON + 1 or frame["close"].isnull().any():
            log.info(
                "S04_LABEL_INVALID signal_date=%s security=%s reason=incomplete_future_path"
                % (label["signal_date"], label["security"])
            )
            continue
        values = [float(value) for value in frame["close"]]
        start = values[0]
        gross = values[-1] / start - 1.0
        net = gross - ROUND_TRIP_COST
        mae = min(value / start - 1.0 for value in values)
        success = int(net >= LABEL_MIN_NET_RETURN and mae >= LABEL_MAX_MAE)
        matured_count += 1
        g.label_total += 1
        g.label_success += success
        if label["selected"]:
            g.selected_label_total += 1
            g.selected_label_success += success
            g.selected_net_sum += net
            log.info(
            "S04_LABEL signal_date=%s mature_date=%s security=%s selected=%s selected_rank=%s score=%.8f "
            "slope=%s r2=%s path_return=%s efficiency_ratio=%s bias_trend_slope=%s "
            "huber_iterations=%s huber_downweighted=%s recent_score=%.8f "
            "huber_score=%s efficiency_score=%s bias_score=%s huber_rank=%s "
            "efficiency_rank=%s bias_rank=%s recent_pass=%s gap=%s gross=%.8f "
            "net=%.8f mae=%.8f success=%s"
            % (
                label["signal_date"],
                today,
                label["security"],
                label["selected"],
                label.get("selected_rank"),
                label["score"],
                "%.10f" % label["slope"] if label.get("slope") is not None else "NA",
                "%.8f" % label["r2"] if label.get("r2") is not None else "NA",
                "%.10f" % label["path_return"] if label.get("path_return") is not None else "NA",
                "%.8f" % label["efficiency_ratio"] if label.get("efficiency_ratio") is not None else "NA",
                "%.10f" % label["bias_trend_slope"] if label.get("bias_trend_slope") is not None else "NA",
                label.get("huber_iterations", "NA"),
                label.get("huber_downweighted", "NA"),
                label["recent_score"],
                label.get("huber_score", "NA"),
                label.get("efficiency_score", "NA"),
                label.get("bias_score", "NA"),
                label.get("huber_rank", "NA"),
                label.get("efficiency_rank", "NA"),
                label.get("bias_rank", "NA"),
                label["recent_pass"],
                label["gap"],
                gross,
                net,
                mae,
                success,
            )
            )
    g.labels = remaining
    if matured_count:
        selected_precision = (
            float(g.selected_label_success) / g.selected_label_total
            if g.selected_label_total
            else 0.0
        )
        unconditional_rate = (
            float(g.label_success) / g.label_total if g.label_total else 0.0
        )
        selected_avg_net = (
            g.selected_net_sum / g.selected_label_total
            if g.selected_label_total
            else 0.0
        )
        log.info(
            "S04_LABEL_SUMMARY date=%s all=%s all_success=%s unconditional_rate=%.8f "
            "selected=%s selected_success=%s selected_precision=%.8f selected_avg_net=%.8f"
            % (
                today,
                g.label_total,
                g.label_success,
                unconditional_rate,
                g.selected_label_total,
                g.selected_label_success,
                selected_precision,
                selected_avg_net,
            )
        )


def _is_month_end(today):
    next_days = get_trade_days(
        start_date=today + datetime.timedelta(days=1),
        end_date=today + datetime.timedelta(days=10),
    )
    if len(next_days) == 0:
        return True
    return next_days[0].month != today.month


def _log_new_orders_and_trades():
    orders = get_orders()
    for order_id, order in orders.items():
        if order_id in g.logged_orders:
            continue
        g.logged_orders.add(order_id)
        log.info(
            "S04_ORDER_AUDIT id=%s security=%s action=%s amount=%s filled=%s price=%s status=%s"
            % (
                order_id,
                order.security,
                getattr(order, "action", None),
                order.amount,
                order.filled,
                order.price,
                order.status,
            )
        )
    trades = get_trades()
    for trade_id, trade in trades.items():
        if trade_id in g.logged_trades:
            continue
        g.logged_trades.add(trade_id)
        amount = getattr(trade, "amount", None)
        price = getattr(trade, "price", None)
        money = getattr(trade, "money", None)
        if money is None and amount is not None and price is not None:
            money = abs(amount * price)
        log.info(
            "S04_TRADE id=%s order_id=%s security=%s amount=%s price=%s money=%s"
            % (
                trade_id,
                getattr(trade, "order_id", None),
                getattr(trade, "security", None),
                amount,
                price,
                money,
            )
        )


def _log_eod(context):
    positions = {
        security: position.total_amount
        for security, position in context.portfolio.positions.items()
        if position.total_amount
    }
    identity_error = abs(
        context.portfolio.available_cash
        + context.portfolio.positions_value
        - context.portfolio.total_value
    )
    position_signature = tuple(sorted(positions.items()))
    position_changed = position_signature != g.last_position_signature
    g.last_position_signature = position_signature
    today = context.current_dt.date()
    violation = context.portfolio.available_cash < -0.01 or identity_error > 0.01
    if not (position_changed or _is_month_end(today) or violation):
        return
    log.info(
        "S04_EOD date=%s mode=%s cash=%.6f positions_value=%.6f total_value=%.6f identity_error=%.10f violation=%s positions=%s"
        % (
            context.current_dt,
            g.mode,
            context.portfolio.available_cash,
            context.portfolio.positions_value,
            context.portfolio.total_value,
            identity_error,
            int(violation),
            positions,
        )
    )
