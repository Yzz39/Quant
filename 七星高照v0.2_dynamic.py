# 克隆自聚宽文章：https://www.joinquant.com/post/69070
# 原标题：【策略蜕变】七星高照ETF轮动策略大变身！ 原作者：旭日东升量化 / 屌丝逆袭量化
#
# 策略名称：七星高照ETF轮动策略-V0.2（动态池版）
# 改造人：Hermes（应用户要求）  改造时间：2026
# ============================================================
# 【V0.2 相对 V1.6 的核心改动 —— 只动"选池"，不动"打分内核"】
#   1. 取消写死的 7 只 ETF 池，改为每日动态构建 universe：
#        硬门槛①：类型 ∈ {etf, lof}（保留原池里的原油/白银 LOF 商品腿，
#                 否则只筛 etf 会丢掉跨资产分散度，反害控回撤）
#        硬门槛②：上市满 250 个自然日（新基数据少、动量失真，剔除）
#        硬门槛③：过去 20 日均成交额 ≥ 9000 万（流动性硬代理，
#                 同时踢掉迷你基 + 流动性幻觉标的，比用基金规模AUM更实时可靠）
#   2. 持仓数 holdings_num 从 1 提到 2（跨资产大池子单押 1 只=白筛）
#   3. 新增【相关性去重】：得分排序后贪心选取，若与已选标的 60 日日收益
#        相关性 |ρ| > 0.7 则跳过——正面对冲"动量榜清一色同主题"的坍塌风险，
#        保住分散红利（这是本次改造最贴合"控回撤"目标的一步）
#   4. 选池/打分逻辑当日缓存，sell 与 buy 共用同一份 target，消除原版
#        sell(ranked[:N]) 与 buy(premium过滤) 口径不一致导致的多余换手
#
# 【仍未解决、需你自己验的历史遗留隐患（见对话点评）】
#   - 过拟合：volume_return_limit=1 的反动量补丁、premium_threshold 值(0.20)
#            与注释(10%)不符、五层开关+一堆魔数 → 必做样本外(OOS)验证
#   - 滑点：万1(0.0001) 对 LOF/低流动品种严重偏低，务必把滑点拉到
#            千3/千5 重跑做成本敏感性，看年化/夏普撑不撑得住
# ============================================================

import numpy as np
import pandas as pd
import math
import builtins
from jqdata import *

# from jqdata import * 会用聚宽的查询聚合函数遮蔽 Python 内置 max/min/sum。
# 本文件自写了近3日跌幅取极值、下单量取极值等逻辑，一律用下划线别名，防遮蔽坑。
_max = builtins.max
_min = builtins.min
_sum = builtins.sum


# ==================== 初始化模块 ====================
def initialize(context):
    """初始化：交易参数、动态池门槛、核心参数、调度任务"""
    # ---------- 交易设置 ----------
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_slippage(PriceRelatedSlippage(0.0001), type="fund")   # ⚠️ 偏低，OOS 时请上调重跑
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0002,
            close_commission=0.0002,
            close_today_commission=0,
            min_commission=5,
        ),
        type="fund",
    )
    set_benchmark("510300.XSHG")   # 改用沪深300ETF作基准（原用白银LOF做基准不合理）

    log.set_level('order', 'error')
    log.set_level('system', 'error')
    log.set_level('strategy', 'debug')
    log.info("========== 策略初始化开始（V0.2 动态池版）==========")

    # ---------- 动态池硬门槛（新增） ----------
    g.universe_types = ['etf', 'lof']   # 保留 LOF 以纳入原油/白银等商品腿
    g.min_list_days = 250               # 上市满 250 自然日才进池
    g.amount_lookback = 20              # 成交额回看天数
    g.min_amount = 9000 * 10000         # 20日均成交额 ≥ 9000 万

    # ---------- 相关性去重（新增） ----------
    g.enable_corr_dedup = True
    g.corr_lookback = 60                # 用 60 日日收益算相关性
    g.corr_threshold = 0.7              # |ρ| > 0.7 视为同质，去重

    # ---------- 核心参数（沿用 V1.6，未动打分内核） ----------
    g.lookback_days = 25                # 动量计算周期
    g.holdings_num = 2                  # ★ 持仓数 1 → 2
    g.defensive_etf = "511880.XSHG"     # 防御ETF（货币基金）
    g.min_money = 5000                  # 最小交易金额

    g.stop_loss = 0.95                  # 固定止损线（-5%）
    g.loss = 0.97                       # 近3日单日跌幅阈值

    g.min_score_threshold = 0           # 最低得分
    g.max_score_threshold = 500.0       # 最高得分

    # ---------- 成交量过滤 ----------
    g.enable_volume_check = True
    g.volume_lookback = 5
    g.volume_threshold = 2
    g.volume_return_limit = 1           # ⚠️ 反动量补丁，OOS 建议关掉对比

    # ---------- 短期动量过滤 ----------
    g.use_short_momentum_filter = True
    g.short_lookback_days = 10
    g.short_momentum_threshold = 0.0

    # ---------- 溢价率过滤 ----------
    g.enable_premium_filter = True
    g.premium_threshold = 0.20          # ⚠️ 值 0.20 与原注释"10%"不符，此处以代码为准

    # ---------- 运行时缓存 ----------
    g.rankings_cache = {'date': None, 'data': None}
    g.targets_cache = {'date': None, 'data': None}

    # ---------- 交易调度 ----------
    run_daily(check_positions, time='09:10')
    run_daily(etf_sell_trade, time='14:00')
    run_daily(etf_buy_trade, time='14:01')

    log.info(f"初始化完成：动态池门槛[上市>{g.min_list_days}天 & 20日均额>{g.min_amount/1e8:.2f}亿]，"
             f"持仓{g.holdings_num}只，动量{g.lookback_days}天，相关性去重{'开' if g.enable_corr_dedup else '关'}(阈值{g.corr_threshold})")
    log.info("========== 策略初始化完成 ==========")


# ==================== 动态 universe 构建（新增核心模块） ====================
def get_dynamic_universe(context):
    """
    每日构建候选池：类型过滤 → 上市时长过滤 → 20日均成交额过滤。
    返回合格代码列表（未算动量，只是把垃圾/迷你/幻觉标的先踢掉）。
    """
    today = context.current_dt.date()

    # 1. 取当日"已上市"的 etf/lof（用 date=today 避免幸存者偏差/前视）
    all_funds = get_all_securities(types=g.universe_types, date=today)
    if all_funds is None or all_funds.empty:
        log.warning("get_all_securities 返回空")
        return []

    # 2. 上市时长过滤
    codes = []
    for code in all_funds.index:
        start = all_funds.loc[code, 'start_date']
        try:
            start_d = start.date() if hasattr(start, 'date') else start
            if (today - start_d).days >= g.min_list_days:
                codes.append(code)
        except Exception:
            continue
    if not codes:
        return []

    # 3. 20日均成交额过滤（用前一交易日为止的完整日线，避免当日盘中半天成交额失真）
    prev_date = get_trade_days(end_date=today, count=2)[0]
    try:
        df = get_price(codes, end_date=prev_date, count=g.amount_lookback,
                       frequency='daily', fields=['money'],
                       skip_paused=False, fq='pre', panel=False)
    except Exception as e:
        log.warning(f"批量取成交额失败: {e}")
        return []
    if df is None or df.empty:
        return []

    avg_amount = df.groupby('code')['money'].mean()
    liquid = avg_amount[avg_amount >= g.min_amount].index.tolist()

    log.info(f"动态池：全市场{len(all_funds)}只 → 上市达标{len(codes)}只 → 流动性达标{len(liquid)}只")
    return liquid


# ==================== 排名缓存 ====================
def get_cached_rankings(context):
    """同一交易日内多次调用结果一致"""
    today = context.current_dt.date()
    if g.rankings_cache['date'] != today:
        log.info("重新计算 ETF 排名（动态池）...")
        universe = get_dynamic_universe(context)
        ranked = get_ranked_etfs(context, universe)
        g.rankings_cache = {'date': today, 'data': ranked}
    else:
        log.debug("使用缓存排名")
    return g.rankings_cache['data']


def get_cached_targets(context):
    """
    统一计算最终目标持仓列表（供 sell/buy 共用，消除口径不一致）：
    得分过滤 → 溢价率过滤 → 相关性去重 → 截断到 holdings_num。
    """
    today = context.current_dt.date()
    if g.targets_cache['date'] == today:
        return g.targets_cache['data']

    ranked = get_cached_rankings(context)
    targets = select_targets(context, ranked)
    g.targets_cache = {'date': today, 'data': targets}
    return targets


# ==================== 核心计算模块（打分内核未动） ====================
def get_ranked_etfs(context, universe):
    """对动态 universe 计算动量得分，过滤后按得分降序返回"""
    etf_metrics = []
    cur_data = get_current_data()
    for etf in universe:
        # 停牌过滤
        if cur_data[etf].paused:
            log.debug(f"{etf} {get_name(etf)} 停牌，跳过")
            continue

        metrics = calculate_momentum_metrics(context, etf)
        if metrics is not None:
            if g.min_score_threshold < metrics['score'] < g.max_score_threshold:
                etf_metrics.append(metrics)
            else:
                log.debug(f"{etf} {metrics['etf_name']} 得分{metrics['score']:.2f}超阈值，过滤")

    etf_metrics.sort(key=lambda x: x['score'], reverse=True)
    return etf_metrics


def calculate_momentum_metrics(context, etf):
    """计算单只 ETF 的动量指标（沿用 V1.6 打分逻辑，未改）"""
    try:
        name = get_name(etf)
        lookback = _max(g.lookback_days, g.short_lookback_days) + 20
        prices = attribute_history(etf, lookback, '1d', ['close', 'high'])
        if len(prices) < g.lookback_days:
            log.debug(f"{etf} {name} 历史数据不足{len(prices)}天，跳过")
            return None

        current_price = get_current_data()[etf].last_price
        price_series = np.append(prices["close"].values, current_price)

        # 1. 成交量过滤（仅当启用且年化收益超阈值）
        if g.enable_volume_check:
            vol_ratio = get_volume_ratio(context, etf)
            if vol_ratio is not None:
                annualized = get_annualized_returns(price_series, g.lookback_days)
                if annualized > g.volume_return_limit:
                    log.info(f"📉 {etf} {name} 放量{vol_ratio:.1f}倍且年化{annualized*100:.1f}%>阈值，过滤")
                    return None

        # 2. 短期动量
        if len(price_series) >= g.short_lookback_days + 1:
            short_return = price_series[-1] / price_series[-(g.short_lookback_days + 1)] - 1
            short_annualized = (1 + short_return) ** (250 / g.short_lookback_days) - 1
        else:
            short_annualized = 0

        if g.use_short_momentum_filter and short_annualized < g.short_momentum_threshold:
            log.debug(f"{etf} {name} 短期动量{short_annualized*100:.1f}%<阈值，过滤")
            return None

        # 3. 长期动量（加权对数线性回归）
        recent = price_series[-(g.lookback_days + 1):]
        y = np.log(recent)
        x = np.arange(len(y))
        weights = np.linspace(1, 2, len(y))
        slope, intercept = np.polyfit(x, y, 1, w=weights)
        annualized_returns = math.exp(slope * 250) - 1

        ss_res = np.sum(weights * (y - (slope * x + intercept)) ** 2)
        ss_tot = np.sum(weights * (y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        score = annualized_returns * r_squared

        # 4. 近3日单日跌幅过滤
        if len(price_series) >= 4:
            day1 = price_series[-1] / price_series[-2]
            day2 = price_series[-2] / price_series[-3]
            day3 = price_series[-3] / price_series[-4]
            if _min(day1, day2, day3) < g.loss:
                log.info(f"⚠️ {etf} {name} 近3日有单日大跌，得分归零")
                score = 0

        return {
            'etf': etf,
            'etf_name': name,
            'annualized_returns': annualized_returns,
            'r_squared': r_squared,
            'score': score,
            'current_price': current_price,
            'short_annualized': short_annualized,
        }

    except Exception as e:
        log.warning(f"计算{etf} {get_name(etf)}时出错: {e}")
        return None


def get_annualized_returns(price_series, lookback_days):
    """加权年化收益率"""
    recent = price_series[-(lookback_days + 1):]
    y = np.log(recent)
    x = np.arange(len(y))
    weights = np.linspace(1, 2, len(y))
    slope, _ = np.polyfit(x, y, 1, w=weights)
    return math.exp(slope * 250) - 1


def get_volume_ratio(context, security, lookback=None, threshold=None):
    """当日成交量 / 过去N日均量，超阈值返回比值否则 None"""
    lookback = lookback or g.volume_lookback
    threshold = threshold or g.volume_threshold
    try:
        name = get_name(security)
        hist = attribute_history(security, lookback, '1d', ['volume'])
        if hist.empty or len(hist) < lookback:
            return None
        avg_vol = hist['volume'].mean()

        today = context.current_dt.date()
        df_vol = get_price(security, start_date=today, end_date=context.current_dt,
                           frequency='1m', fields=['volume'], skip_paused=False, fq='pre')
        if df_vol is None or df_vol.empty:
            return None
        current_vol = df_vol['volume'].sum()
        ratio = current_vol / avg_vol if avg_vol > 0 else 0
        if ratio > threshold:
            log.debug(f"{security} {name} 成交量比{ratio:.2f}>{threshold}")
            return ratio
        return None
    except Exception as e:
        log.warning(f"成交量计算失败 {security}: {e}")
        return None


# ==================== 相关性去重（新增） ====================
def get_return_series(etf, n, context):
    """取近 n 日日收益序列（pandas Series，index 为日期）用于算相关性"""
    try:
        hist = attribute_history(etf, n + 1, '1d', ['close'])
        if hist is None or len(hist) < n:
            return None
        ret = hist['close'].pct_change().dropna()
        if len(ret) < int(n * 0.6):   # 数据太少不参与去重判断
            return None
        return ret
    except Exception as e:
        log.warning(f"取{etf}收益序列失败: {e}")
        return None


def select_targets(context, ranked):
    """
    从排名结果贪心选出最终持仓：
    得分过滤 → 溢价率过滤 → 相关性去重 → 截断到 holdings_num。
    """
    targets = []
    ret_cache = {}

    prev_date = None
    if g.enable_premium_filter:
        prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]

    for m in ranked:
        if len(targets) >= g.holdings_num:
            break

        etf = m['etf']
        # 1. 得分过滤
        if m['score'] < g.min_score_threshold:
            continue

        # 2. 溢价率过滤
        if g.enable_premium_filter:
            premium, _, _ = get_premium_rate(etf, prev_date)
            if premium is None:
                log.info(f"⚠️ {etf} {get_name(etf)} 无溢价率，跳过")
                continue
            if premium > g.premium_threshold:
                log.info(f"🚫 {etf} {get_name(etf)} 溢价率{premium*100:.2f}%>阈值，跳过")
                continue

        # 3. 相关性去重
        if g.enable_corr_dedup and targets:
            ret_new = get_return_series(etf, g.corr_lookback, context)
            if ret_new is not None:
                too_corr = False
                for s in targets:
                    ret_old = ret_cache.get(s)
                    if ret_old is None:
                        continue
                    c = ret_new.corr(ret_old)
                    if c is not None and not math.isnan(c) and abs(c) > g.corr_threshold:
                        log.info(f"🔗 {etf} {get_name(etf)} 与已选{s}相关性{c:.2f}>{g.corr_threshold}，去重跳过")
                        too_corr = True
                        break
                if too_corr:
                    continue
                ret_cache[etf] = ret_new
            else:
                # 拿不到收益序列，保守起见仍纳入但不缓存（无法参与后续去重）
                pass

        targets.append(etf)
        log.info(f"🎯 目标{len(targets)}: {etf} {m['etf_name']} 得分{m['score']:.4f} "
                 f"年化{m['annualized_returns']*100:.2f}% R²={m['r_squared']:.4f}")

    return targets


# ==================== 溢价率获取 ====================
def get_premium_rate(code, date):
    """溢价率=(场内价-净值)/净值，用前一日净值，适合盘中判断"""
    price_data = get_price(code, start_date=date, end_date=date,
                           frequency='daily', fields=['close'])
    if price_data.empty:
        log.debug(f"{date} {code} 无价格数据")
        return None, None, None
    price = price_data['close'].iloc[0]

    net_data = get_extras('unit_net_value', code, start_date=date, end_date=date, df=True)
    if net_data.empty or pd.isna(net_data[code].iloc[0]):
        try:
            q = query(finance.FUND_NET_VALUE).filter(
                finance.FUND_NET_VALUE.code == code,
                finance.FUND_NET_VALUE.day == date
            )
            net_df = finance.run_query(q)
            if not net_df.empty:
                net_value = net_df['net_value'].iloc[0]
            else:
                log.debug(f"{date} {code} 无净值数据")
                return None, None, None
        except Exception:
            log.debug(f"{date} {code} 查询净值异常")
            return None, None, None
    else:
        net_value = net_data[code].iloc[0]

    premium_rate = (price - net_value) / net_value
    return premium_rate, price, net_value


# ==================== 卖出模块 ====================
def check_positions(context):
    """开盘打印持仓"""
    for sec in context.portfolio.positions:
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            log.info(f"📊 持仓：{sec} {get_name(sec)} 数量{pos.total_amount} "
                     f"成本{pos.avg_cost:.3f} 现价{pos.price:.3f}")


def etf_sell_trade(context):
    """卖出不在目标列表的持仓 + 固定止损 + 溢价率检查"""
    log.info("========== 卖出操作开始 ==========")

    targets = get_cached_targets(context)
    # 无目标且防御可用 → 防御标的作为唯一目标（供卖出判断）
    if not targets and check_defensive_etf_available(context):
        targets = [g.defensive_etf]
    target_set = set(targets)

    # 1. 卖出不在目标的持仓
    for sec in list(context.portfolio.positions.keys()):
        if sec not in target_set:
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                if smart_order_target_value(sec, 0, context):
                    log.info(f"📤 卖出不在目标的持仓：{sec} {get_name(sec)}")

    # 2. 固定止损
    for sec in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[sec]
        if pos.total_amount > 0:
            if pos.price <= pos.avg_cost * g.stop_loss:
                if smart_order_target_value(sec, 0, context):
                    loss_pct = (pos.price / pos.avg_cost - 1) * 100
                    log.info(f"🚨 固定止损卖出：{sec} {get_name(sec)} 亏损{loss_pct:.2f}%")

    # 3. 溢价率检查
    if g.enable_premium_filter:
        prev_date = get_trade_days(end_date=context.current_dt.date(), count=2)[0]
        for sec in list(context.portfolio.positions.keys()):
            pos = context.portfolio.positions[sec]
            if pos.total_amount > 0:
                premium, _, _ = get_premium_rate(sec, prev_date)
                if premium is not None and premium > g.premium_threshold:
                    if smart_order_target_value(sec, 0, context):
                        log.info(f"🚨 溢价过高 {sec} {get_name(sec)} 溢价率{premium*100:.2f}%，卖出")

    log.info("========== 卖出操作完成 ==========")


# ==================== 买入模块 ====================
def etf_buy_trade(context):
    """按目标等权买入（含防御模式），先清仓不在目标的持仓再建仓"""
    log.info("========== 买入操作开始 ==========")

    ranked = get_cached_rankings(context)
    log.info("=== 排名前5 ===")
    for i, m in enumerate(ranked[:5]):
        log.info(f"排名{i+1}: {m['etf']} {m['etf_name']} 得分{m['score']:.4f} "
                 f"年化{m['annualized_returns']*100:.2f}% R²={m['r_squared']:.4f}")

    targets = get_cached_targets(context)

    # 防御模式
    if not targets:
        if check_defensive_etf_available(context):
            targets = [g.defensive_etf]
            log.info(f"🛡️ 进入防御模式：{g.defensive_etf} {get_name(g.defensive_etf)}")
        else:
            log.info("💤 无目标且防御不可用，保持空仓")
            return

    # 先卖后买：若还有不在目标的持仓，等卖出完成
    to_sell = [s for s in context.portfolio.positions if s not in targets]
    to_sell = [s for s in to_sell if context.portfolio.positions[s].total_amount > 0]
    if to_sell:
        log.info(f"尚有持仓待卖出：{[(s, get_name(s)) for s in to_sell]}，等下一轮再建仓")
        return

    # 等权分配
    total_val = context.portfolio.total_value
    target_per_etf = total_val / len(targets)

    for etf in targets:
        current_val = 0
        if etf in context.portfolio.positions:
            pos = context.portfolio.positions[etf]
            if pos.total_amount > 0:
                current_val = pos.total_amount * pos.price
        # 5% 容差调仓
        if abs(current_val - target_per_etf) > target_per_etf * 0.05 or current_val == 0:
            if smart_order_target_value(etf, target_per_etf, context):
                action = "买入" if current_val < target_per_etf else "调仓"
                log.info(f"📦 {action}：{etf} {get_name(etf)} 目标金额{target_per_etf:.2f}")

    log.info("========== 买入操作完成 ==========")


# ==================== 辅助函数 ====================
def get_name(security):
    try:
        return get_current_data()[security].name
    except Exception:
        return "未知"


def check_defensive_etf_available(context):
    """防御ETF是否可交易（未停牌、未涨跌停）"""
    data = get_current_data()
    etf = g.defensive_etf
    if data[etf].paused:
        return False
    if data[etf].last_price >= data[etf].high_limit:
        return False
    if data[etf].last_price <= data[etf].low_limit:
        return False
    return True


def smart_order_target_value(security, target_value, context):
    """智能下单：处理停牌、涨跌停、最小交易金额、T+1、100股整数倍"""
    data = get_current_data()
    name = get_name(security)

    if data[security].paused:
        log.info(f"{security} {name} 停牌，跳过")
        return False

    price = data[security].last_price
    if price == 0:
        log.info(f"{security} {name} 当前价0，跳过")
        return False

    target_amount = int(target_value / price)
    target_amount = (target_amount // 100) * 100
    if target_amount <= 0 and target_value > 0:
        target_amount = 100

    cur_pos = context.portfolio.positions.get(security, None)
    cur_amount = cur_pos.total_amount if cur_pos else 0
    diff = target_amount - cur_amount

    if diff > 0:   # 买入查涨停
        if data[security].last_price >= data[security].high_limit:
            log.info(f"{security} {name} 涨停，跳过买入")
            return False
    elif diff < 0:  # 卖出查跌停
        if data[security].last_price <= data[security].low_limit:
            log.info(f"{security} {name} 跌停，跳过卖出")
            return False

    trade_val = abs(diff) * price
    if 0 < trade_val < g.min_money:
        log.info(f"{security} {name} 交易额{trade_val:.2f}<{g.min_money}，跳过")
        return False

    if diff < 0:   # T+1
        closeable = cur_pos.closeable_amount if cur_pos else 0
        if closeable == 0:
            log.info(f"{security} {name} 当天买入不可卖出")
            return False
        diff = -_min(abs(diff), closeable)

    if diff != 0:
        order_result = order(security, diff)
        if order_result:
            log.info(f"{'📥 买入' if diff>0 else '📤 卖出'} {security} {name} 数量{abs(diff)} 价{price:.3f}")
            return True
        else:
            log.warning(f"下单失败: {security} {name} 数量{diff}")
            return False
    return False
