# -*- coding: utf-8 -*-
"""
脚本功能：在聚宽上独立验证“动态ETF池”的构建逻辑，不连接任何动量评分和交易下单。
标的范围：信号日当时存在的ETF/fund；排除特殊结构、现金类重复产品和数据不完整标的。
信号时序：只在自然月最后一个交易日运行，名单与行情均使用信号日及以前的数据。
池子规则：上市满252个交易日、最近60日行情质量合格；L0 使用60日平均成交额固定门槛，
          L3 使用60日成交额中位数与资金容量/类别内分位数/绝对下限的最大值；
          先按经济资产类别覆盖选代表，再保护代表并对剩余标的做Pearson/Spearman组合相关性去重，货币ETF独立保留。
输出内容：每个信号日的候选数量、类别覆盖率、每类代表、排除原因、最终池成员和不变量检查。
交易行为：本脚本不持仓、不下单、不计算M0-M3G分数，只用于验证动态ETF池。
研究区间：默认2015-01-01至2020-12-31；前252个交易日为数据预热期，修改区间应另建版本并重新登记。
适用限制：名称过滤不能替代基金底层指数、历史规模和跨境交易时区审计；回测日志不代表实盘收益。
"""

from jqdata import *
import builtins
import datetime
import math

import pandas as pd


# from jqdata import * 可能覆盖Python内置聚合函数；研究逻辑必须固定使用原生实现。
_py_any = builtins.any
_py_max = builtins.max
_py_sum = builtins.sum


# ============================== 研究配置 ==============================

TEST_START = datetime.date(2015, 1, 1)
TEST_END = datetime.date(2020, 12, 31)

CASH_SECURITY = "511880.XSHG"
CORE = (
    "510300.XSHG",
    "511010.XSHG",
    "518880.XSHG",
    CASH_SECURITY,
)
CORE_CASH_EQUIVALENT_SECURITIES = (
    "159001.XSHE",
    "159003.XSHE",
    "159005.XSHE",
)
CORE_BOND_SECURITIES = (
    "511010.XSHG",
    "511220.XSHG",
)
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
AUDIT_SECURITIES = (
    "513100.XSHG",  # 纳指ETF
    "513500.XSHG",  # 标普500ETF
    "159941.XSHE",  # 纳指ETF广发
)
ELIGIBILITY_DAYS = 252
LIQUIDITY_DAYS = 60
CORRELATION_DAYS = 126
MIN_CORRELATION_OBSERVATIONS = 80
MIN_DUPLICATE_CORRELATION = 0.00
MAX_DUPLICATE_CORRELATION = 0.80
MAX_LIQUID_CANDIDATES = 100
MAX_DYNAMIC_RISK_POOL_SIZE = 25
MIN_DYNAMIC_RISK_ASSETS = 5
DYNAMIC_DATA_CHUNK_SIZE = 180
MIN_AVG_MONEY = 50_000_000.0
INITIAL_CAPITAL = 100_000.0
DATA_FIELDS = ["open", "high", "low", "close", "volume", "money"]

# 流动性研究版本：L0 保留原固定门槛作为对照，L3 为主要测试版本。
# 针对早期ETF成交较低及几十万元资金规模，本版本允许最高2%的日成交参与率；
# 10万元资金容量门槛为600万元，由300万元绝对下限兜底，并使用类别内30%分位数。
LIQUIDITY_MODE = "L3"
LIQUIDITY_QUANTILE = 0.30
LIQUIDITY_CAPITAL_LEVERAGE = 1.0
MAX_PARTICIPATION = 0.02
LIQUIDITY_BUFFER = 1.2
ABSOLUTE_LIQUIDITY_FLOOR = 3_000_000.0
MIN_ACTIVE_DAYS_RATIO = 0.95

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

# 聚宽部分版本对单独的['etf']历史查询返回不完整；合并查询etf/lof，
# 再在元数据层排除LOF和分级产品，可兼容动态池的实际返回口径。
ETF_QUERY_TYPES = ["etf", "lof"]

ENGINE_VERSION = "pool_validator_category_coverage_v0.9_core_protected_classification_fix"


# ============================== 聚宽初始化 ==============================

def initialize(context):
    if LIQUIDITY_MODE not in ("L0", "L3"):
        raise ValueError("unsupported LIQUIDITY_MODE: %s" % LIQUIDITY_MODE)

    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)

    g.pool_check_count = 0
    g.pool_failure_count = 0

    log.info(
        "POOL_VALIDATOR_VERSION %s start=%s end=%s cash=%s "
        "eligibility_days=%d liquidity_days=%d liquidity_mode=%s "
        "min_avg_money=%.2f initial_capital=%.2f liquidity_quantile=%.2f "
        "capital_leverage=%.2f max_participation=%.4f liquidity_buffer=%.2f "
        "absolute_floor=%.2f active_days_ratio=%.2f "
        "correlation_days=%d correlation_floor=%.2f correlation_cap=%.2f "
        "correlation_methods=pearson_spearman max_liquid=%d "
        "max_pool=%d min_risk_assets=%d"
        % (
            ENGINE_VERSION,
            TEST_START,
            TEST_END,
            CASH_SECURITY,
            ELIGIBILITY_DAYS,
            LIQUIDITY_DAYS,
            LIQUIDITY_MODE,
            MIN_AVG_MONEY,
            INITIAL_CAPITAL,
            LIQUIDITY_QUANTILE,
            LIQUIDITY_CAPITAL_LEVERAGE,
            MAX_PARTICIPATION,
            LIQUIDITY_BUFFER,
            ABSOLUTE_LIQUIDITY_FLOOR,
            MIN_ACTIVE_DAYS_RATIO,
            CORRELATION_DAYS,
            MIN_DUPLICATE_CORRELATION,
            MAX_DUPLICATE_CORRELATION,
            MAX_LIQUID_CANDIDATES,
            MAX_DYNAMIC_RISK_POOL_SIZE,
            MIN_DYNAMIC_RISK_ASSETS,
        )
    )
    log.info(
        "POOL_CATEGORY_CONFIG order=%s min_representatives=%s"
        % (ETF_CATEGORY_ORDER, CATEGORY_MIN_REPRESENTATIVES)
    )
    log.info(
        "POOL_CORE_CONFIG core=%s cash_equivalent=%s bond_overrides=%s"
        % (CORE, CORE_CASH_EQUIVALENT_SECURITIES, CORE_BOND_SECURITIES)
    )

    # 只做盘后诊断，不能产生交易订单。
    run_daily(validate_pool, time="after_close")


def validate_pool(context):
    signal_date = context.current_dt.date()
    if signal_date < TEST_START or signal_date > TEST_END:
        return
    if not _is_month_end(signal_date):
        return

    g.pool_check_count += 1
    try:
        result = _build_dynamic_pool(signal_date)
        issues = _check_pool_invariants(result)
        passed = int(len(issues) == 0)
        if not passed:
            g.pool_failure_count += 1

        diagnostics = result["diagnostics"]
        log.info(
            "POOL_METADATA_COUNTS date=%s etf_pool=%d fund=%d merged=%d recognized_etf=%d"
            % (
                signal_date,
                diagnostics["metadata_query_counts"].get("etf_pool", 0),
                diagnostics["metadata_query_counts"].get("fund", 0),
                diagnostics["raw_count"],
                diagnostics["recognized_etf_count"],
            )
        )
        log.info(
            "POOL_CHECK date=%s raw=%d metadata_pass=%d market_quality_pass=%d "
            "liquid_pass=%d "
            "liquid_risk=%d risk_pool=%d cash_available=%s final_size=%d "
            "category_available=%d category_covered=%d category_coverage=%.4f "
            "liquidity_mode=%s liquidity_metric=%s liquidity_threshold=%.2f "
            "quantile_threshold=%.2f capital_floor=%.2f active_days_min=%d "
            "warmup=%s metadata_errors=%s price_errors=%s "
            "metadata_warnings=%s invariant_pass=%s issues=%s"
            % (
                signal_date,
                diagnostics["raw_count"],
                diagnostics["metadata_pass_count"],
                diagnostics["market_quality_pass_count"],
                diagnostics["liquid_pass_count"],
                diagnostics["uncapped_risk_count"],
                diagnostics["risk_pool_count"],
                result["cash_available"],
                len(result["pool"]),
                diagnostics["category_available_count"],
                diagnostics["category_covered_count"],
                diagnostics["category_coverage_ratio"],
                diagnostics["liquidity_mode"],
                diagnostics["liquidity_metric"],
                diagnostics["liquidity_threshold"],
                diagnostics["liquidity_quantile_threshold"],
                diagnostics["liquidity_capital_floor"],
                diagnostics["liquidity_active_days_min"],
                diagnostics["warmup"],
                diagnostics["metadata_query_failures"],
                diagnostics["price_query_failures"],
                diagnostics["metadata_query_warnings"],
                passed,
                issues,
            )
        )
        log.info(
            "POOL_CORE date=%s available=%s selected=%s missing=%s"
            % (
                signal_date,
                diagnostics.get("core_available", []),
                diagnostics.get("core_selected", []),
                diagnostics.get("core_missing", []),
            )
        )
        for category in ETF_CATEGORY_ORDER:
            representative = result["category_representatives"].get(category, "NA")
            covered = int(
                diagnostics["category_pool_counts"].get(category, 0)
                >= CATEGORY_MIN_REPRESENTATIVES[category]
            )
            available = int(diagnostics["category_liquid_counts"].get(category, 0) > 0)
            log.info(
                "POOL_CATEGORY_SUMMARY date=%s category=%s label=%s "
                "metadata=%d quality=%d liquid=%d selected=%d "
                "available=%d covered=%d representative=%s "
                "quantile_threshold=%.2f threshold=%.2f"
                % (
                    signal_date,
                    category,
                    CATEGORY_LABELS[category],
                    diagnostics["category_metadata_counts"][category],
                    diagnostics["category_quality_counts"][category],
                    diagnostics["category_liquid_counts"][category],
                    diagnostics["category_pool_counts"][category],
                    available,
                    covered,
                    representative,
                    diagnostics["liquidity_quantiles_by_category"][category],
                    diagnostics["liquidity_thresholds_by_category"][category],
                )
            )
        log.info(
            "POOL_EXCLUDE_SUMMARY date=%s reasons=%s"
            % (signal_date, diagnostics["exclusion_counts"])
        )
        log.info(
            "POOL_EXCLUDE_SAMPLE date=%s samples=%s"
            % (signal_date, diagnostics["exclusion_samples"])
        )

        for rank, security in enumerate(result["risk_pool"], start=1):
            metadata = result["metadata"][security]
            metrics = result["liquidity_metrics"][security]
            log.info(
                "POOL_MEMBER date=%s rank=%d security=%s query_type=%s "
                "name=%s category=%s liquidity_metric=%s liquidity_value=%.2f "
                "mean_money=%.2f median_money=%.2f valid_days=%d active_ratio=%.4f"
                % (
                    signal_date,
                    rank,
                    security,
                    metadata[0],
                    metadata[2],
                    result["category_by_security"].get(security, "unknown"),
                    diagnostics["liquidity_metric"],
                    result["avg_money"].get(security, 0.0),
                    metrics["mean_money"],
                    metrics["median_money"],
                    metrics["valid_days"],
                    metrics["active_days_ratio"],
                )
            )

        if result["cash_available"]:
            cash_metadata = result["metadata"].get(CASH_SECURITY)
            cash_metrics = result["liquidity_metrics"][CASH_SECURITY]
            log.info(
                "POOL_CASH date=%s security=%s query_type=%s name=%s "
                "category=%s liquidity_metric=%s liquidity_value=%.2f mean_money=%.2f "
                "median_money=%.2f valid_days=%d active_ratio=%.4f"
                % (
                    signal_date,
                    CASH_SECURITY,
                    cash_metadata[0] if cash_metadata else "NA",
                    cash_metadata[2] if cash_metadata else "NA",
                    result["category_by_security"].get(CASH_SECURITY, "cash"),
                    diagnostics["liquidity_metric"],
                    result["avg_money"].get(CASH_SECURITY, 0.0),
                    cash_metrics["mean_money"],
                    cash_metrics["median_money"],
                    cash_metrics["valid_days"],
                    cash_metrics["active_days_ratio"],
                )
            )

        for duplicate in result["duplicates"]:
            log.info(
                "POOL_DUPLICATE date=%s security=%s representative=%s "
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

        for security in AUDIT_SECURITIES:
            metadata = result["metadata"].get(security)
            metrics = result["liquidity_metrics"].get(security)
            reason = result["exclusion_reasons"].get(security, "")
            category = result["category_by_security"].get(security, "unknown")
            if security in result["risk_pool"]:
                status = "selected"
            elif reason:
                status = "excluded"
            elif security in result["liquid"]:
                status = "liquid_not_selected"
            elif metadata is None:
                status = "not_in_metadata"
            else:
                status = "not_selected_unknown"
            metric_value = (
                metrics.get(diagnostics["liquidity_metric"], 0.0)
                if metrics else 0.0
            )
            target_threshold = diagnostics["liquidity_thresholds_by_category"].get(
                category,
                diagnostics["liquidity_threshold"],
            )
            log.info(
                "POOL_TARGET_AUDIT date=%s security=%s name=%s status=%s "
                "category=%s reason=%s liquidity_metric=%s liquidity_value=%.2f "
                "threshold=%.2f valid_days=%d active_ratio=%.4f"
                % (
                    signal_date,
                    security,
                    metadata[2] if metadata else "NA",
                    status,
                    category,
                    reason or "NA",
                    diagnostics["liquidity_metric"],
                    metric_value,
                    target_threshold,
                    metrics["valid_days"] if metrics else 0,
                    metrics["active_days_ratio"] if metrics else 0.0,
                )
            )

        # record用于在聚宽图表中快速观察池子规模，不替代明细日志。
        record(
            pool_raw=diagnostics["raw_count"],
            pool_metadata=diagnostics["metadata_pass_count"],
            pool_liquid=diagnostics["liquid_pass_count"],
            pool_risk=len(result["risk_pool"]),
            pool_cash=int(result["cash_available"]),
            pool_warmup=int(diagnostics["warmup"]),
            pool_invariant=passed,
            pool_category_available=diagnostics["category_available_count"],
            pool_category_covered=diagnostics["category_covered_count"],
            pool_category_coverage=diagnostics["category_coverage_ratio"],
            pool_liquidity_threshold_m=diagnostics["liquidity_threshold"] / 1e6,
            pool_liquidity_quantile_m=(
                diagnostics["liquidity_quantile_threshold"] / 1e6
            ),
            pool_liquidity_capital_floor_m=(
                diagnostics["liquidity_capital_floor"] / 1e6
            ),
        )
    except Exception as error:
        g.pool_failure_count += 1
        log.error(
            "POOL_CHECK_ERROR date=%s error_type=%s error=%s"
            % (signal_date, type(error).__name__, error)
        )


def after_trading_end(context):
    """兼容聚宽不同回测模板，最终输出池子检查计数。"""
    today = context.current_dt.date()
    if g.pool_check_count and (_is_month_end(today) or today == TEST_END):
        log.info(
            "POOL_VALIDATOR_EOD date=%s checks=%d failures=%d"
            % (
                today,
                g.pool_check_count,
                g.pool_failure_count,
            )
        )


# ============================== 动态池构建 ==============================

def _build_dynamic_pool(signal_date):
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
    metadata_pass = []

    for security in sorted(metadata):
        reason = _metadata_exclusion_reason(
            security,
            metadata[security],
            signal_date,
            listing_cutoff,
        )
        if reason is None:
            metadata_pass.append(security)
        else:
            _increment_reason(exclusion_counts, reason)
            exclusion_reasons[security] = reason
            _append_exclusion_sample(
                exclusion_samples,
                reason,
                security,
                metadata[security],
            )

    required_days = _py_max(CORRELATION_DAYS + 1, LIQUIDITY_DAYS)
    panels, price_query_failures = _fetch_history(
        metadata_pass,
        signal_date,
        required_days,
    )
    market_candidates = []
    liquidity_metrics = {}

    for security in metadata_pass:
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
    liquidity_threshold = liquidity_config["threshold"]
    liquid = []
    avg_money = {}
    liquidity_threshold_by_security = {}
    for security in market_candidates:
        amount = liquidity_metrics[security][liquidity_metric_key]
        category = category_by_security[security]
        security_threshold = liquidity_config["thresholds_by_category"][category]
        liquidity_threshold_by_security[security] = security_threshold
        if amount < security_threshold:
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
        # 保留旧字段名供现有审计代码兼容；其值是当前模式实际使用的指标。
        avg_money[security] = amount

    cash_available = CASH_SECURITY in liquid
    risk_liquid_all = [
        security for security in liquid if security != CASH_SECURITY
    ]
    risk_liquid_all.sort(key=lambda security: (-avg_money[security], security))
    uncapped_risk_count = len(risk_liquid_all)

    # 先为每个有合格标的的经济类别预留一个席位，再用全局流动性补足候选上限。
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

    # 先锁定原四资产；后续相关性去重只允许淘汰新增候选。
    core_available = [security for security in CORE if security in liquid]
    core_risk_available = [security for security in CORE if security in risk_liquid]
    for security in core_risk_available:
        if len(risk_pool) >= MAX_DYNAMIC_RISK_POOL_SIZE:
            pool_limit_count += 1
            exclusion_reasons[security] = "outside_pool_size_limit"
            continue
        risk_pool.append(security)
        category_representatives.setdefault(
            category_by_security.get(security),
            security,
        )

    # 再为尚未覆盖的类别预留流动性最高的一只；已由核心资产覆盖的类别
    # 不再强行加入第二只代表，新增标的稍后统一经过相关性过滤。
    for category in RISK_CATEGORY_ORDER:
        if category in category_representatives:
            continue
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

    # 第二轮填充剩余席位；此时相关性去重不会删除已经预留的类别代表。
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

    category_metadata_counts = _category_counts(
        metadata_pass,
        category_by_security,
    )
    category_quality_counts = _category_counts(
        market_candidates,
        category_by_security,
    )
    category_liquid_counts = _category_counts(
        liquid,
        category_by_security,
    )
    category_pool_counts = _category_counts(
        pool,
        category_by_security,
    )
    available_categories = [
        category for category in ETF_CATEGORY_ORDER
        if category_liquid_counts[category] > 0
    ]
    covered_categories = [
        category for category in available_categories
        if category_pool_counts[category] >= CATEGORY_MIN_REPRESENTATIVES[category]
    ]
    coverage_ratio = (
        float(len(covered_categories)) / len(available_categories)
        if available_categories else 1.0
    )

    diagnostics = {
        "raw_count": len(metadata),
        "metadata_pass_count": len(metadata_pass),
        "market_quality_pass_count": len(market_candidates),
        "liquid_pass_count": len(liquid),
        "uncapped_risk_count": uncapped_risk_count,
        "risk_pool_count": len(risk_pool),
        "core_available": core_available,
        "core_risk_available": core_risk_available,
        "core_selected": [security for security in CORE if security in pool],
        "core_missing": [security for security in CORE if security not in pool],
        "core_unavailable": [security for security in CORE if security not in liquid],
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
        "liquidity_threshold": liquidity_threshold,
        "liquidity_quantile_threshold": liquidity_config["quantile_threshold"],
        "liquidity_capital_floor": liquidity_config["capital_floor"],
        "liquidity_active_days_min": liquidity_config["active_days_min"],
        "liquidity_thresholds_by_category": liquidity_config[
            "thresholds_by_category"
        ],
        "liquidity_quantiles_by_category": liquidity_config[
            "quantile_thresholds_by_category"
        ],
        "category_metadata_counts": category_metadata_counts,
        "category_quality_counts": category_quality_counts,
        "category_liquid_counts": category_liquid_counts,
        "category_pool_counts": category_pool_counts,
        "category_available_count": len(available_categories),
        "category_covered_count": len(covered_categories),
        "category_coverage_ratio": coverage_ratio,
        "category_available": available_categories,
        "category_covered": covered_categories,
        "category_unavailable": [
            category for category in ETF_CATEGORY_ORDER
            if category_liquid_counts[category] == 0
        ],
    }
    return {
        "pool": pool,
        "risk_pool": risk_pool,
        "cash_available": cash_available,
        "metadata": metadata,
        "avg_money": avg_money,
        "liquidity_metrics": liquidity_metrics,
        "liquidity_threshold_by_security": liquidity_threshold_by_security,
        "market_candidates": market_candidates,
        "liquid": liquid,
        "category_by_security": category_by_security,
        "category_representatives": category_representatives,
        "exclusion_reasons": exclusion_reasons,
        "duplicates": duplicates,
        "diagnostics": diagnostics,
    }


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
    if MAX_LIQUID_CANDIDATES < len(RISK_CATEGORY_ORDER) + len(CORE):
        raise ValueError("MAX_LIQUID_CANDIDATES is smaller than category count")

    reserved = [security for security in CORE if security in securities]
    for category in RISK_CATEGORY_ORDER:
        candidates = [
            security for security in securities
            if category_by_security.get(security) == category
        ]
        if candidates and candidates[0] not in reserved:
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
    """使用信号日名称和交易代码做点时分类；未命中特征的权益ETF归入行业主题。"""
    name = str(metadata[2] if len(metadata) >= 3 else "")
    upper_name = name.upper()
    upper_security = str(security).upper()

    if (
        security == CASH_SECURITY
        or security in CORE_CASH_EQUIVALENT_SECURITIES
        or _py_any(
            keyword in name for keyword in CASH_NAME_KEYWORDS
        )
    ):
        return "cash"
    if security in CORE_BOND_SECURITIES:
        return "bond"
    if security in BROAD_EQUITY_SECURITY_OVERRIDES:
        return "broad_equity"
    if _py_any(
        keyword in name
        for keyword in (
            "国债",
            "地方债",
            "政金债",
            "国开",
            "债券",
            "利率债",
            "信用债",
            "可转债",
            "城投债",
            "短融",
            "债",
        )
    ):
        return "bond"
    if _py_any(
        keyword in name
        for keyword in (
            "黄金",
            "商品ETF",
            "商品",
            "白银",
            "豆粕",
            "能源化工",
            "原油",
            "有色金属期货",
        )
    ):
        return "commodity"
    if upper_security.startswith("513") or _py_any(
        keyword in upper_name
        for keyword in (
            "纳指",
            "纳斯达克",
            "标普",
            "恒生",
            "港股",
            "中概",
            "日经",
            "德国",
            "DAX",
            "法国",
            "印度",
            "海外",
            "全球",
            "东南亚",
            "亚太",
            "美国",
            "日本",
            "英国",
            "沙特",
            "越南",
            "道琼斯",
        )
    ):
        return "cross_border_equity"
    if _py_any(
        keyword in name
        for keyword in ("红利", "股息", "低波", "高股息")
    ):
        return "dividend_style"
    if _py_any(
        keyword in name
        for keyword in (
            "沪深300",
            "中证300",
            "中证500",
            "中证1000",
            "中证2000",
            "中证A50",
            "中证A500",
            "上证50",
            "上证180",
            "上证指数",
            "深证成指",
            "中小",
            "创业板ETF",
            "创业板50",
            "科创50",
            "科创100",
            "科创200",
            "双创",
            "国证2000",
            "国证1000",
            "国证A指",
            "宽基",
            "大盘",
            "小盘",
            "中盘",
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
                "POOL_METADATA_FAIL date=%s type=%s error=%s"
                % (signal_date, query_type, error)
            )
            continue
        if table is None or len(table) == 0:
            query_warnings.append("%s:empty" % query_type)
            log.warn(
                "POOL_METADATA_EMPTY date=%s type=%s" % (signal_date, query_type)
            )
            continue
        query_counts[query_type] = len(table)
        samples = []
        for index, (security, row) in enumerate(table.iterrows()):
            name = _security_name(row)
            if index < 3:
                samples.append(
                    "%s|row_type=%s|name=%s"
                    % (security, _security_row_type(row), name)
                )
            if security not in metadata:
                metadata[security] = (
                    query_type,
                    row,
                    name,
                    _is_etf_metadata(query_type, row, name),
                )
        log.info(
            "POOL_METADATA_SAMPLE date=%s query_type=%s samples=%s"
            % (signal_date, query_type, samples)
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
    """取得上市满252个交易日所需的最晚上市日。"""
    trade_days = get_trade_days(
        end_date=signal_date,
        count=ELIGIBILITY_DAYS,
    )
    if len(trade_days) < ELIGIBILITY_DAYS:
        return None
    first_day = trade_days[0]
    return first_day.date() if hasattr(first_day, "date") else first_day


def _metadata_exclusion_reason(security, metadata, signal_date, listing_cutoff):
    query_type, row, name, is_etf = metadata
    upper_name = name.upper()
    row_type = _security_row_type(row).strip().lower()

    if security != CASH_SECURITY and not is_etf:
        return "non_etf_fund"
    if row_type in ("lof", "fja", "fjb", "分级基金a", "分级基金b"):
        return "excluded_product_type"
    if _py_any(
        keyword.upper() in upper_name for keyword in EXCLUDED_NAME_KEYWORDS
    ):
        return "excluded_product_type"
    if security != CASH_SECURITY and (
        security in CORE_CASH_EQUIVALENT_SECURITIES
        or _py_any(keyword in name for keyword in CASH_NAME_KEYWORDS)
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


# ============================== 行情完整性 ==============================

def _fetch_history(securities, end_date, count):
    """分批获取历史数据，避免全市场逐只请求。"""
    frames = []
    query_failures = []
    for start in range(0, len(securities), DYNAMIC_DATA_CHUNK_SIZE):
        chunk = securities[start : start + DYNAMIC_DATA_CHUNK_SIZE]
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
                "POOL_PRICE_FAIL date=%s chunk_start=%d size=%d error=%s"
                % (end_date, start, len(chunk), error)
            )
            query_failures.append(
                "start=%d,size=%d,%s" % (start, len(chunk), type(error).__name__)
            )
            continue
        normalized = _normalize_price_frame(frame, chunk)
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


def _normalize_price_frame(frame, securities):
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


def _market_data_quality(security, panels, required_days):
    """检查行情完整性并返回流动性统计，门槛在横截面汇总后统一计算。"""
    if _py_any(
        field not in panels or security not in panels[field]
        for field in DATA_FIELDS
    ):
        return "missing_market_columns", None

    close_tail = panels["close"][security].iloc[-required_days:]
    if len(close_tail) != required_days or close_tail.isnull().any():
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
    ).apply(pd.to_numeric, errors="coerce")
    liquidity_valid = recent.notnull().all(axis=1)
    liquidity_valid &= recent["volume"] > 0
    if LIQUIDITY_MODE == "L3":
        # L3 允许少量停牌/缺失，但不接受负成交额或非正价格。
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
    """计算 L0/L3 的流动性指标、门槛和审计参数。"""
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
        # threshold 是全局硬下限；实际筛选使用 thresholds_by_category。
        "threshold": hard_floor,
        "quantile_threshold": global_quantile,
        "capital_floor": capital_floor,
        "active_days_min": int(math.ceil(LIQUIDITY_DAYS * MIN_ACTIVE_DAYS_RATIO)),
        "thresholds_by_category": thresholds,
        "quantile_thresholds_by_category": quantile_thresholds,
    }


# ============================== 相关性去重 ==============================

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
        # 取两种秩/线性相关中较高者，避免单一算法低估单调但非线性的关系。
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

    for security in diagnostics.get("core_risk_available", []):
        if security not in risk_pool:
            issues.append("core_missing:%s" % security)

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


# ============================== 日期工具 ==============================

def _is_month_end(today):
    next_days = get_trade_days(
        start_date=today + datetime.timedelta(days=1),
        end_date=today + datetime.timedelta(days=10),
    )
    return len(next_days) == 0 or next_days[0].month != today.month
