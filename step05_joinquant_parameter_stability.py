# Step 05: preregistered lookback and rebalance-frequency stability grid.
# Paste this file into JoinQuant and change only RUN_MODE, LOOKBACK and
# REBALANCE_INTERVAL for each run. M0 uses RUN_MODE='momentum'; M1 uses
# RUN_MODE='m1_absolute'; M2 uses RUN_MODE='m2_recent_confirm';
# M2R uses RUN_MODE='m2_ranked_recent';
# M3A uses RUN_MODE='m3_ols_slope'; M3B uses RUN_MODE='m3b_efficiency';
# M3C uses RUN_MODE='m3c_bias_trend'; M3D uses RUN_MODE='m3d_wls_slope';
# M3E uses RUN_MODE='m3e_huber_slope';
# M3F uses RUN_MODE='m3f_equal_rank';
# M3G uses RUN_MODE='m3g_efficiency_rank'.
from jqdata import *
import datetime
import math


RUN_MODE = "momentum"
LOOKBACK = 252
REBALANCE_INTERVAL = 20
ENGINE_VERSION = "v0.1"
CODE_VERSION = "step05_%s_lb%s_f%s_%s" % (
    RUN_MODE,
    LOOKBACK,
    REBALANCE_INTERVAL,
    ENGINE_VERSION,
)
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

CORE = ["510300.XSHG", "511010.XSHG", "518880.XSHG", "511880.XSHG"]
ALLOWED_LOOKBACKS = (252, 126, 63, 31, 14)
ALLOWED_REBALANCE_INTERVALS = (20, 10, 5, 1)
RECENT_LOOKBACK_BY_MOMENTUM = {252: 42, 126: 21, 63: 11, 31: 5, 14: 2}
BIAS_MA_WINDOW_BY_MOMENTUM = {252: 180, 126: 90, 63: 45, 31: 22, 14: 10}
BIAS_TREND_POINTS_BY_MOMENTUM = {252: 50, 126: 25, 63: 13, 31: 6, 14: 3}
RECENT_LOOKBACK = RECENT_LOOKBACK_BY_MOMENTUM.get(LOOKBACK)
BIAS_MA_WINDOW = BIAS_MA_WINDOW_BY_MOMENTUM.get(LOOKBACK)
BIAS_TREND_POINTS = BIAS_TREND_POINTS_BY_MOMENTUM.get(LOOKBACK)
HUBER_EPSILON = 1.345
HUBER_MAX_ITERATIONS = 50
HUBER_TOLERANCE = 1e-10
FUSION_FACTORS = ("huber", "efficiency", "bias")
ELIGIBILITY_DAYS = 253 if LOOKBACK == 252 else 252
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


def initialize(context):
    if RUN_MODE not in SIGNAL_MODES:
        raise ValueError(
            "unsupported RUN_MODE: %s" % RUN_MODE
        )
    if LOOKBACK not in ALLOWED_LOOKBACKS:
        raise ValueError("unsupported LOOKBACK: %s" % LOOKBACK)
    if REBALANCE_INTERVAL not in ALLOWED_REBALANCE_INTERVALS:
        raise ValueError(
            "unsupported REBALANCE_INTERVAL: %s" % REBALANCE_INTERVAL
        )

    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)
    set_option("order_volume_ratio", 0.005)
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
    g.rebalance_trade_day_count = 0

    starting_cash = context.portfolio.starting_cash
    log.info(
        "S05_CODE_VERSION %s"
        % CODE_VERSION
    )
    log.info(
        "S05_CONFIG mode=%s selection_policy=%s capital=%.2f lookback=%d recent_lookback=%d "
        "rebalance_interval=%d bias_ma_window=%d bias_trend_points=%d label_horizon=%d "
        "label_min_net=%.4f label_max_mae=%.4f huber_epsilon=%.3f huber_max_iter=%d "
        "train_start=%s train_end=%s"
        % (
            g.mode,
            M3_SELECTION_POLICY if g.mode in M3_MODES else "mode_default",
            starting_cash,
            LOOKBACK,
            RECENT_LOOKBACK,
            REBALANCE_INTERVAL,
            BIAS_MA_WINDOW,
            BIAS_TREND_POINTS,
            LABEL_HORIZON,
            LABEL_MIN_NET_RETURN,
            LABEL_MAX_MAE,
            HUBER_EPSILON,
            HUBER_MAX_ITERATIONS,
            TRAIN_START,
            TRAIN_END,
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


def after_close_audit(context):
    today = context.current_dt.date()
    _update_mature_labels(today)

    if today < TRAIN_END and _is_rebalance_day(today):
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
    if not g.baseline_started:
        if len(eligible) < len(CORE):
            log.info(
                "S04_WAIT_COMMON date=%s eligible=%s required=%s reasons=%s"
                % (signal_date, eligible, len(CORE), reasons)
            )
            return
        g.baseline_started = True
        log.info("S04_BASELINE_START date=%s" % signal_date)

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


def _eligible_universe(signal_date):
    tables = {
        "etf": get_all_securities(["etf"], date=signal_date),
        "fund": get_all_securities(["fund"], date=signal_date),
    }
    metadata = {}
    for query_type in ("etf", "fund"):
        table = tables[query_type]
        for security in CORE:
            if security in table.index and security not in metadata:
                metadata[security] = (query_type, table.loc[security])

    current_data = get_current_data()
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
    avg_money = {}

    for security in CORE:
        if security not in metadata:
            reasons[security] = "not_in_etf_or_fund_metadata"
            log.info("S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s" % (signal_date, security, reasons[security]))
            continue

        query_type, row = metadata[security]
        start_date = row.start_date.date() if hasattr(row.start_date, "date") else row.start_date
        end_date = row.end_date.date() if hasattr(row.end_date, "date") else row.end_date
        trade_days = get_trade_days(start_date=start_date, end_date=signal_date)
        if len(trade_days) < ELIGIBILITY_DAYS:
            reasons[security] = "listing_days=%s" % len(trade_days)
            log.info("S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s" % (signal_date, security, reasons[security]))
            continue
        if end_date < signal_date:
            reasons[security] = "ended=%s" % end_date
            log.info("S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s" % (signal_date, security, reasons[security]))
            continue
        if getattr(current_data[security], "paused", False):
            reasons[security] = "paused"
            log.info("S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s" % (signal_date, security, reasons[security]))
            continue

        liquidity = get_price(
            security,
            end_date=signal_date,
            count=LIQUIDITY_DAYS,
            frequency="1d",
            fields=DATA_FIELDS,
            fq="none",
        )
        if len(liquidity) != LIQUIDITY_DAYS or liquidity[DATA_FIELDS].isnull().any().any():
            reasons[security] = "incomplete_60d_fields"
            log.info("S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s" % (signal_date, security, reasons[security]))
            continue
        money = float(liquidity["money"].mean())
        avg_money[security] = money
        if money < MIN_AVG_MONEY:
            reasons[security] = "avg_money=%.2f" % money
            log.info("S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s" % (signal_date, security, reasons[security]))
            continue

        prices = get_price(
            security,
            end_date=signal_date,
            count=LOOKBACK + 1,
            frequency="1d",
            fields=["close"],
            fq="pre",
        )
        if len(prices) != LOOKBACK + 1 or prices["close"].isnull().any():
            reasons[security] = "incomplete_%sd_close" % (LOOKBACK + 1)
            log.info("S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s" % (signal_date, security, reasons[security]))
            continue
        close_values = [float(value) for value in prices["close"].tolist()]
        invalid_indices = [
            index
            for index, value in enumerate(close_values)
            if not math.isfinite(value) or value <= 0
        ]
        if invalid_indices:
            reasons[security] = "invalid_close count=%s first_index=%s first_value=%s" % (
                len(invalid_indices),
                invalid_indices[0],
                close_values[invalid_indices[0]],
            )
            log.info("S04_ELIGIBILITY date=%s security=%s eligible=0 reason=%s" % (signal_date, security, reasons[security]))
            continue

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
                bias_trend_slope = _bias_trend_score(
                    close_values,
                    ma_window=BIAS_MA_WINDOW,
                    trend_points=BIAS_TREND_POINTS,
                )
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
                bias_trend_slope = _bias_trend_score(
                    close_values,
                    ma_window=BIAS_MA_WINDOW,
                    trend_points=BIAS_TREND_POINTS,
                )
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
    """Return the OLS slope of normalized price/MA over the scaled trend segment."""
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


def _update_mature_labels(today):
    remaining = []
    matured_count = 0
    for label in g.labels:
        trade_days = get_trade_days(start_date=label["signal_date"], end_date=today)
        if len(trade_days) < LABEL_HORIZON + 1:
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


def _is_rebalance_day(today):
    """Use one frozen phase: the Nth, 2Nth, ... trading day from TRAIN_START."""
    if today < TRAIN_START or today >= TRAIN_END:
        return False
    g.rebalance_trade_day_count += 1
    return g.rebalance_trade_day_count % REBALANCE_INTERVAL == 0


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
