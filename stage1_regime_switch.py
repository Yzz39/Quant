# -*- coding: utf-8 -*-
"""
阶段1: 单层择时开关 (Regime Switch, 攻守整体二选一)
================================================================
目的: 在做轮动之前, 先诚实验证一个问题 ——
      "根据市场状态在【进攻池】和【防守池】之间整体切换", 到底有没有价值?
      跑不赢"纯持有防守池"和"攻守静态混合买入持有", 这个想法当场作废, 别自欺.

★ 结构(单层, 无轮动):
   开关(裁判) --> 判定当前 A股宽基处于"可进攻"还是"该防守"状态
     · 可进攻 --> 全仓【进攻池】: 创业板 + 纳指 (等权)
     · 该防守 --> 全仓【防守池】: 红利低波 + 国债 (红利为主, 国债压舱)

★ 开关判据(只看已发生的事实, 不预测拐点 = 右侧交易):
   在【裁判指数】(默认沪深300)上:
     · 趋势: 收盘价 > MA200      (在长期均线上方)
     · 波动率刹车: 已实现波动率的历史分位 < 阈值 (不在高波区制)
   两者都满足 --> 原始信号=进攻; 否则 --> 原始信号=防守.
   再套 K=3 确认状态机(信号连续 K 次异于当前状态才换档), 治 whipsaw.
   全部 shift(1): 今日仓位只用昨日及之前的信息, 严防未来函数.

★ 必比基线(缺一不可, 否则无法判断开关有没有价值):
   基线0  纯持有 红利低波            <- 及格线(防守池单腿)
   基线1  纯持有 创业板              <- 进攻单腿(看开关有没有帮你躲开回撤)
   基线2  攻守四腿静态混合 买入持有   <- 关键对照: 不切换只混合, 开关能否跑赢它?
   策略   开关切换

★ 数据事实(绕不开):
   · 创业板指 399006.XSHE  指数, 2010+ (确认可用)
   · 纳指    513100.XSHG  ETF, 2013-05 上市 —— 聚宽无海外指数, 只能用ETF, 历史被它卡住
   · 红利低波 见 RED_LOWVOL: 优先中证红利低波指数, 保底中证红利000922(长史)
   · 国债    000012.XSHG  上证国债指数(避险腿; 票息口径不完美, 压测可接受)
   混用"指数+ETF"是压测约定(非可交易回测), 与 etf_rotation_stress_test_longhistory 一致.

★ 运行环境: 聚宽【研究环境 Notebook】(不是回测器). 本地无 jqdata, 只能 py_compile 语法校验.
   填码前先跑【第0步 代码验证】坐实 code, 别信记忆猜后缀.
"""
import numpy as np
import pandas as pd

# ==================== 配置区 ====================
START = '2013-01-01'
END   = '2026-07-08'

# ---- 标的 ----
RED_LOWVOL = '000922.XSHG'   # 红利低波替身: 保底=中证红利; 若确认中证红利低波指数可取(H30269/930146)则换上, 更贴ETF
ATTACK = {
    '创业板': '399006.XSHE',   # 创业板指(价格版), 2010+
    '纳指':   '513100.XSHG',   # 纳指ETF(无海外指数只能用它), 2013-05上市
}
DEFENSE = {
    '红利低波': RED_LOWVOL,
    '国债':    '000012.XSHG',   # 上证国债指数
}
GAUGE_CODE = '000300.XSHG'     # 裁判指数: A股宽基市场状态代表(默认沪深300)
GAUGE_NAME = '沪深300'
#   注: 进攻池含纳指(美股), 用A股宽基当裁判来门控整池, 是阶段1的简化取舍(整池二选一).
#       "各市场用各自regime分别门控"是阶段2的细化, 阶段1先不做, 免得分不清哪层在起作用.

# ---- 池内权重(阶段1定死不优化) ----
ATTACK_W  = {'创业板': 0.5, '纳指': 0.5}          # 进攻池等权
DEFENSE_W = {'红利低波': 0.6, '国债': 0.4}         # 防守池: 红利为主+国债压舱(可调旋钮, 别用逆波动率否则国债吃满仓)

# ---- 开关参数 ----
MA_WINDOW     = 200    # 长期趋势均线(交易日)
VOL_WINDOW    = 20     # 已实现波动率回看窗
VOL_PCTL_WIN  = 252    # 波动率分位的历史参照窗(1年)
VOL_PCTL_TH   = 0.80   # 波动率刹车阈值: 分位 >= 此值(高波前20%)判防守
K_CONFIRM     = 3      # 状态确认次数(信号连续K次异于当前状态才换档), 治whipsaw
SIGNAL_FREQ   = 'W'    # 信号评估频率: 'D'每日 / 'W'每周. 周频=K=3约3周确认, 平衡灵敏与防抖

# ---- 成本 ----
COST_RATE = 0.0006     # 单边成本(佣金+滑点近似): ETF约万3佣金+滑点, 单边取万6较保守. 换手时按turnover计.

# ---- 样本内外切分 ----
IS_END = '2020-12-31'  # 样本内截止(定参); 样本外=之后至今(检验, 不许回头调参)

# ---- 危机窗口(重点看开关有没有帮你在这几段躲进防守) ----
CRISIS = {
    '2015股灾': ('2015-06-12', '2015-09-30'),
    '2016熔断': ('2016-01-01', '2016-02-29'),
    '2018熊市': ('2018-01-24', '2019-01-04'),
    '2020疫情': ('2020-01-13', '2020-03-23'),
    '2022回撤': ('2021-12-31', '2022-10-31'),
}

# ==================== 第0步: 代码验证(填码前先跑坐实) ====================
# A. 红利低波补搜(smart-beta不在index清单, 换宽词):
#   idx = get_all_securities(types=['index'])
#   for kw in ['红利','低波','低波动']:
#       print('=====', kw); print(idx[idx.display_name.str.contains(kw)][['display_name']])
#   # 若出现"中证红利低波动"就用它的code(更贴ETF); 没有就保底 000922.XSHG 中证红利.
#
# B. 纳指ETF / 各腿 get_price 验证能否取到 + 起始日:
#   for code in ['513100.XSHG','399006.XSHE','000922.XSHG','000012.XSHG','000300.XSHG']:
#       try:
#           df = get_price(code, start_date='2013-01-01', end_date='2024-01-01', fq='post')
#           print('%-14s OK 起%s 共%d条' % (code, df.index.min().date(), len(df)))
#       except Exception as e:
#           print('%-14s FAIL %s' % (code, e))
#   # 全部OK后整体运行 main().


# ==================== 数据加载: 逐腿单独取价(研究环境稳健写法) ====================
# 不用多标的 get_price+pivot(研究环境返回结构不同, 易得空表->收益恒0). 逐腿取再拼.
def load_closes(legs):
    data = {}
    for name, code in legs.items():
        try:
            df = get_price(code, start_date=START, end_date=END,
                           frequency='daily', fields=['close'], fq='post')
            s = df['close'].dropna() if df is not None else None
            if s is not None and len(s) > 0:
                data[name] = s
            else:
                print('!! %s(%s) 取到空数据' % (name, code))
        except Exception as e:
            print('!! %s(%s) 取价失败: %s' % (name, code, e))
    if not data:
        raise RuntimeError('全部腿取价失败, 检查 code')
    wide = pd.DataFrame(data).sort_index()
    print('数据区间:', wide.index.min().date(), '~', wide.index.max().date(),
          ' | 有效腿数:', wide.shape[1], '/', len(legs))
    for n in wide.columns:
        s = wide[n].dropna()
        print('  %-8s %s  (%d条)' % (n, s.index.min().date(), len(s)))
    return wide


# ==================== 开关: 裁判指数 -> 每日原始信号 -> K确认状态机 ====================
def compute_regime(gauge_close):
    """返回一个 Series(index=每个交易日, 值='A'进攻 / 'D'防守),
    已 shift(1): 今日仓位用昨日及之前信息, 无未来函数."""
    close = gauge_close.dropna()
    ma = close.rolling(MA_WINDOW).mean()
    above = close > ma                                  # 趋势: 在MA200上方
    ret = close.pct_change()
    vol = ret.rolling(VOL_WINDOW).std() * np.sqrt(252)  # 已实现年化波动率
    # 波动率历史分位: 最新值在过去VOL_PCTL_WIN窗内的分位(0~1, 越高越处高波区)
    def pctl(x):
        return float((x[-1] >= x).mean())
    vol_pctl = vol.rolling(VOL_PCTL_WIN).apply(pctl, raw=True)
    # 原始信号: 趋势在上方 且 不在高波区 -> 进攻; 否则防守
    raw_attack = above & (vol_pctl < VOL_PCTL_TH)
    raw = raw_attack.map(lambda b: 'A' if b else 'D')

    # 信号评估频率: 周频则在每周最后交易日取原始信号, 其余日沿用
    if SIGNAL_FREQ == 'W':
        wk = close.index.to_series().dt.to_period('W')
        is_eval = wk.ne(wk.shift(-1)).values   # 每周最后一个交易日
    else:
        is_eval = np.ones(len(close), dtype=bool)

    # K确认状态机: 信号连续K次(在评估点上)异于当前确认状态才换档
    confirmed = 'D'   # 冷启动默认防守(保守)
    streak = 0
    out = []
    warm = MA_WINDOW + VOL_PCTL_WIN   # 预热期: 指标未成形前一律防守
    for i, d in enumerate(close.index):
        if i < warm or (isinstance(raw.iloc[i], float) and np.isnan(raw.iloc[i])):
            out.append('D'); continue
        if is_eval[i]:
            r = raw.iloc[i]
            if r != confirmed:
                streak += 1
                if streak >= K_CONFIRM:
                    confirmed = r; streak = 0
            else:
                streak = 0
        out.append(confirmed)
    state = pd.Series(out, index=close.index, name='regime')
    return state.shift(1).fillna('D')   # 今日仓位用昨日确认状态


# ==================== 回测引擎: 金额记账 + turnover成本 ====================
def targets_for(state):
    if state == 'A':
        return dict(ATTACK_W)
    return dict(DEFENSE_W)

def run_switch(closes, state):
    """按每日确认状态在攻守池间整体切换. 金额记账避免权重漂移偏差.
    换档(或月度漂移校正)时按 |Δ权重| 计单边成本."""
    rets = closes.pct_change().fillna(0.0)
    dates = closes.index
    month_key = dates.to_series().dt.to_period('M')
    is_month = month_key.ne(month_key.shift(1)).values

    hold = {}          # name -> 市值
    cash = 1.0
    prev_state = None
    navs = []
    n_switch = 0
    for i, d in enumerate(dates):
        if hold:
            hold = {c: v * (1.0 + rets[c].iloc[i]) for c, v in hold.items()}
        total = float(np.nansum(list(hold.values()))) + cash
        st = state.iloc[i] if d in state.index else 'D'
        # 换档 或 月度漂移校正 时再平衡
        flip = (st != prev_state)
        if flip or is_month[i]:
            tg = targets_for(st)
            # 只在标的已有数据时建仓
            tg = {c: w for c, w in tg.items()
                  if c in closes.columns and not np.isnan(closes[c].iloc[i])}
            wsum = sum(tg.values())
            if wsum > 0:
                tg = {c: w / wsum for c, w in tg.items()}   # 归一(防某腿无数据)
            # turnover成本: 目标市值 vs 当前市值的绝对差 / 总资产
            new_val = {c: total * w for c, w in tg.items()}
            turnover = 0.0
            allk = set(new_val) | set(hold)
            for c in allk:
                turnover += abs(new_val.get(c, 0.0) - hold.get(c, 0.0))
            cost = (turnover / total) * COST_RATE * total if total > 0 else 0.0
            total_after = total - cost
            hold = {c: total_after * w for c, w in tg.items()}
            cash = 0.0
            if flip and prev_state is not None:
                n_switch += 1
            prev_state = st
        navs.append(total)
    nav = pd.Series(navs, index=dates, name='开关切换')
    return nav, n_switch


# ==================== 基线 ====================
def buy_hold(closes, name):
    s = closes[name].dropna()
    return (s / s.iloc[0]).rename('持有_' + name)

def static_blend(closes, weights):
    """攻守四腿静态混合买入持有(不切换), 月度再平衡回目标权重(公平对照)."""
    rets = closes.pct_change().fillna(0.0)
    dates = closes.index
    month_key = dates.to_series().dt.to_period('M')
    is_month = month_key.ne(month_key.shift(1)).values
    hold = {}; cash = 1.0; navs = []
    for i, d in enumerate(dates):
        if hold:
            hold = {c: v * (1.0 + rets[c].iloc[i]) for c, v in hold.items()}
        total = float(np.nansum(list(hold.values()))) + cash
        if is_month[i]:
            tg = {c: w for c, w in weights.items()
                  if c in closes.columns and not np.isnan(closes[c].iloc[i])}
            wsum = sum(tg.values())
            if wsum > 0:
                tg = {c: w / wsum for c, w in tg.items()}
                hold = {c: total * w for c, w in tg.items()}; cash = 0.0
        navs.append(total)
    return pd.Series(navs, index=dates, name='静态混合')


# ==================== 绩效指标 ====================
def max_drawdown(nav):
    roll = nav.cummax()
    return (nav / roll - 1.0).min()

def metrics(nav):
    nav = nav.dropna()
    n = len(nav)
    years = n / 252.0
    total = nav.iloc[-1] / nav.iloc[0] - 1.0
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0 if years > 0 else np.nan
    rets = nav.pct_change().dropna()
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else np.nan
    mdd = max_drawdown(nav)
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    vol = rets.std() * np.sqrt(252)
    return dict(total=total, cagr=cagr, sharpe=sharpe, mdd=mdd, calmar=calmar, vol=vol)

def window_mdd(nav, a, b):
    sub = nav.loc[a:b]
    return max_drawdown(sub) if len(sub) > 5 else np.nan

def print_perf_table(title, navs_dict):
    print('\n' + '=' * 70)
    print(title)
    print('=' * 70)
    print('%-14s %8s %8s %7s %9s %7s %7s' %
          ('策略', '总收益', '年化', '夏普', '最大回撤', 'Calmar', '波动率'))
    for name, nav in navs_dict.items():
        m = metrics(nav)
        print('%-14s %7.1f%% %7.2f%% %7.3f %8.2f%% %7.2f %6.1f%%' %
              (name, m['total'] * 100, m['cagr'] * 100, m['sharpe'],
               m['mdd'] * 100, m['calmar'], m['vol'] * 100))


# ==================== 主流程 ====================
def main():
    # 1) 取数(可交易腿 + 裁判指数)
    legs = {}
    legs.update(ATTACK); legs.update(DEFENSE)
    closes = load_closes(legs)
    gauge = load_closes({GAUGE_NAME: GAUGE_CODE})[GAUGE_NAME]

    # 对齐: 以可交易腿的交易日为准
    gauge = gauge.reindex(closes.index).ffill()

    # 2) 开关信号
    state = compute_regime(gauge)
    # 统计攻守占比
    valid = state.loc[closes.dropna(how='all').index]
    a_ratio = (valid == 'A').mean()
    print('\n开关状态占比: 进攻 %.1f%% / 防守 %.1f%%' % (a_ratio * 100, (1 - a_ratio) * 100))

    # 3) 策略 + 基线
    nav_sw, n_sw = run_switch(closes, state)
    print('开关换档次数: %d 次 (全期)' % n_sw)

    blend_w = {}   # 攻守静态混合: 攻守各半, 池内按各自权重
    for c, w in ATTACK_W.items():   blend_w[c] = 0.5 * w
    for c, w in DEFENSE_W.items():  blend_w[c] = 0.5 * w

    navs = {
        '持有红利低波': buy_hold(closes, '红利低波'),
        '持有创业板':   buy_hold(closes, '创业板'),
        '静态混合':     static_blend(closes, blend_w),
        '开关切换':     nav_sw,
    }
    # 全期从共同起点对齐
    start = max(v.dropna().index[0] for v in navs.values())
    navs = {k: (v.loc[start:] / v.loc[start:].iloc[0]) for k, v in navs.items()}

    # 4) 全期表
    print_perf_table('全期绩效 (共同起点 %s ~ %s)' % (start.date(), closes.index[-1].date()), navs)

    # 5) 样本内 / 样本外(关键: 开关的优势在OOS还在不在?)
    navs_is = {k: (v.loc[:IS_END] / v.loc[:IS_END].iloc[0]) for k, v in navs.items()
               if len(v.loc[:IS_END]) > 60}
    navs_oos = {k: (v.loc[IS_END:] / v.loc[IS_END:].iloc[0]) for k, v in navs.items()
                if len(v.loc[IS_END:]) > 60}
    print_perf_table('样本内 IS (<=%s, 定参区间)' % IS_END, navs_is)
    print_perf_table('样本外 OOS (%s 之后, 检验区间)' % IS_END, navs_oos)

    # 6) 危机窗口回撤(看开关有没有帮你躲开)
    print('\n' + '=' * 70)
    print('危机窗口 最大回撤 (开关的核心价值: 该防守时躲进防守池)')
    print('=' * 70)
    order = ['持有创业板', '持有红利低波', '静态混合', '开关切换']
    print('%-10s' % '危机窗口' + ''.join('%12s' % k for k in order))
    for name, (a, b) in CRISIS.items():
        row = '%-10s' % name
        for k in order:
            dd = window_mdd(navs[k], a, b)
            row += '%11.1f%%' % (dd * 100) if not np.isnan(dd) else '%12s' % 'n/a'
        print(row)

    # 7) 判据提示
    print('\n' + '-' * 70)
    print('判据: 开关切换 若在【全期+OOS】的 Calmar/回撤 都跑不赢"静态混合"和"持有红利低波",')
    print('      则单层择时无价值, 阶段2轮动免谈. 反之才有资格往阶段2加进攻池轮动.')

    # 画图(研究环境可显示)
    try:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(12, 5))
        for k, v in navs.items():
            ax.plot(v.index, v.values, label=k)
        ax.set_title('Stage1 Regime Switch vs Baselines')
        ax.legend(); ax.grid(alpha=0.3); ax.set_ylabel('NAV')
        plt.tight_layout(); plt.show()
    except Exception as e:
        print('绘图跳过:', e)

    return navs, state


if __name__ == '__main__':
    main()
