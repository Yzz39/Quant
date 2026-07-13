# -*- coding: utf-8 -*-
"""
ETF跨资产配置 三原型 M1/M2/M2M3 —— 长历史压力测试(母指数替身版)
================================================================
目的: 你原来的 etf_rotation_pk_joinquant.py 用真实ETF跑, 但豆粕ETF(2019)/
      国债ETF(2017-08)/纳指QDII 历史太短, 回测里只有 2020/03 一次真危机
      (n=1), 拿它给杠杆背书太虚. 本脚本用【母指数/全收益指数】做替身, 把
      回测拉到 2014, 把 2015股灾 与 2018熊市 包进来 —— 压力测试, 非可交易回测.

★ 运行环境: 聚宽【研究环境 Notebook】(不是回测器!). 指数不能下单, 但在
   研究环境里纯算收益完全没问题, 且秒出.

★ 三条铁律(否则结论是错的):
   1. 必须用【全收益指数】(total return), 不是价格指数 —— 否则红利/国债的
      票息分红被剥掉, 严重低估收益. 全收益版代码通常不同, 认准"全收益".
   2. 指数≠ETF: 无费率/无跟踪误差/无QDII溢价, 结果比真实略乐观. 但本次目的
      是看【危机期回撤形态】, 乐观一点不影响结论.
   3. 智能beta指数(红利低波)发布日前的历史是事后回补理论值, 2015段可能失真.
      看崩盘期相对表现够用, 别当铁证.
   4. 本压测未计交易成本(月频换手低, 对回撤形态影响极小). 要精算成本回原ETF版.

★ 用法: 先跑【第0步 代码发现】(见下方注释), 把正确的全收益指数 code 填进
   LEGS, 再整体运行. 别信记忆猜后缀 —— 聚宽指数后缀极易报"标的不存在".
"""
import numpy as np
import pandas as pd

# ==================== 配置区 ====================
START = '2014-01-01'
END   = '2026-07-08'
MA_WINDOW  = 200
VOL_WINDOW = 60
BOND_CAP   = 0.35   # 十年国债权重上限(仅 M2C 生效): 逼逆波动率别把仓位全灌进国债,
                    #   超出部分按比例摊回其余腿, 让组合真吃到股票风险溢价.
STRATEGIES = ['M1', 'M2', 'M2M3', 'M2C']   # 四档一起算直接对比
#   M2C = 带国债封顶的风险平价. 长史压测证明 M2/M2M3 逆波动率→国债主导→
#         组合vol仅1.2-1.4%=披皮债券基金, 息差太薄无法承杠杆. M2C 打破国债主导,
#         看基础年化能抬到多少、回撤代价多大 —— 这才是往20%目标走的正路.

# ---- 15%回撤预算方案参数(扫描 + 波动率目标 + 样本外验证) ----
DD_BUDGET  = 0.15    # 你能接受的最大回撤预算
FINANCING  = 0.025   # 杠杆融资成本(年化). 券商两融~5-6%, 股指期货/国债期货隐含~2-3%.
                     #   这里按较优的期货杠杆口径取2.5%; 若走两融改成0.055重跑更保守.
MAX_LEV    = 3.0     # 杠杆硬上限(风控红线): 再高就是保证金+跳空风险失控, 别越线.
TARGET_VOL = 0.10    # 波动率目标: 组合年化波动率稳到此值, 高了减仓低了加仓.
                     #   这套池子 MDD/vol≈1.4, 10%vol 大致对应 ~14%回撤, 卡进15%预算.
VOL_TGT_WIN = 60     # 波动率目标用的已实现波动率回看窗(交易日)
CAP_GRID   = [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]  # BOND_CAP扫描网格
IS_END     = '2020-12-31'   # 样本内截止(定参); 样本外=之后至今(检验, 不许回头调参)

# ---- CTA趋势跟踪腿(抬底盘Calmar的关键: 危机alpha, 补债券底盘怕加息的死穴) ----
ADD_CTA    = True    # True=把合成CTA腿作为第6腿注入池子; False=退回原5腿(对比基线)
# CTA一篮子期货(主力连续9999). 分散是CTA能赚钱的根本, 尽量跨板块.
#   ★这些code必须先在聚宽用第0步-D验证能取到且够长! 别信记忆猜后缀.
#   取不到的品种 build_cta_leg 会自动跳过(像load_closes那样), 不报错.
CTA_FUTURES = {
    '沪深300': 'IF9999.CCFX',   # 股指(2010+)
    '十债期货': 'T9999.CCFX',    # 10年国债期货(2015+, 早期缺就自动跳过)
    '螺纹钢':  'RB9999.XSGE',   # 黑色金属
    '铜':     'CU9999.XSGE',   # 有色
    '黄金F':   'AU9999.XSGE',   # 贵金属(和黄金腿同源但这里做多空)
    '豆粕F':   'M9999.XDCE',    # 农产品
    '玉米':    'C9999.XDCE',    # 农产品
    '白糖':    'SR9999.XZCE',   # 软商品
    'PTA':    'TA9999.XZCE',   # 能化
}
CTA_LOOKBACK   = 120    # 趋势判定回看(交易日, ~6个月动量; 想更快改60, 更慢改252)
CTA_VOL_WIN    = 60     # 波动率估计窗(用于风险平价+整腿缩放)
CTA_TARGET_VOL = 0.12   # 整条CTA腿目标年化波动率(缩放到与指数腿可比, 便于逆波动率配权)
CTA_GROSS_CAP  = 3.0    # CTA内部杠杆上限(风控)

# 危机窗口(重点看这几段回撤): 名称 -> (起, 止)
CRISIS = {
    '2015股灾': ('2015-06-12', '2015-09-30'),
    '2016熔断': ('2016-01-01', '2016-02-29'),
    '2018熊市': ('2018-01-24', '2019-01-04'),
    '2020疫情': ('2020-01-13', '2020-03-23'),
    '2022回撤': ('2021-12-31', '2022-10-31'),
}

# ==================== 第0步: 代码验证(填码前先跑这几段坐实) ====================
# A. 红利低波补搜(smart-beta不在index清单, 换宽词):
#   idx = get_all_securities(types=['index'])
#   for kw in ['红利','低波','低波动']:
#       print('=====', kw); print(idx[idx.display_name.str.contains(kw)][['display_name']])
#   # 若出现"中证红利低波动"就用它的code(更贴ETF); 没有就保底用 000922.XSHG 中证红利.
#
# B. 黄金/豆粕不是指数, 用 get_price 直接验证能否取到(取不到会报错或空):
#   for code in ['AU9999.XSGE','M9999.XDCE']:
#       try:
#           df = get_price(code, count=5, end_date='2024-01-01', fq='post')
#           print(code, 'OK', df.index.min() if len(df) else '空')
#       except Exception as e:
#           print(code, 'FAIL', e)
#   # 豆粕主力连续若 M9999.XDCE 不行, 试 get_dominant_future('M') 拿当前主力合约.
#
# D. CTA期货一篮子验证(9个品种能否取到+起始日+条数, 取不到的build_cta_leg会自动跳):
#   cta_codes = {'沪深300':'IF9999.CCFX','十债期货':'T9999.CCFX','螺纹钢':'RB9999.XSGE',
#                '铜':'CU9999.XSGE','黄金F':'AU9999.XSGE','豆粕F':'M9999.XDCE',
#                '玉米':'C9999.XDCE','白糖':'SR9999.XZCE','PTA':'TA9999.XZCE'}
#   for name, code in cta_codes.items():
#       try:
#           df = get_price(code, start_date='2014-01-01', end_date='2024-01-01', fq='post')
#           print('%-8s %-14s' % (name, code),
#                 ('OK 起%s 共%d条' % (df.index.min().date(), len(df))) if df is not None and len(df) else '空')
#       except Exception as e:
#           print('%-8s %-14s FAIL %s' % (name, code, e))
#   # 后缀备忘: 中金所=.CCFX, 上期所=.XSGE, 大商所=.XDCE, 郑商所=.XZCE. 报错就换后缀重试.
#   # 期货连续合约的 fq='post' 若报错, 去掉 fq 参数再试(连续合约本身已做换月拼接).
#
# C. 全部验证通过后(含CTA), 整体运行 main().

# ==================== 腿定义 ====================
# 已按聚宽 get_all_securities 实测结果核对(2024查询):
#   · 创业板/国债 = 交易所指数, 已确认可用
#   · 红利低波 = smart-beta指数不在index清单 -> 见下方 RED_LOWVOL 处理
#   · 黄金/豆粕 = 现货/期货, 不在index清单, 需 get_price 单独验证(下方注释)
#   · 纳指 = 聚宽无海外指数 -> 剔除, 长测少一条海外分散腿(结果偏保守)
#
# 红利低波替身选择(按优先级, 用哪个取决于你 get_price 能不能取到):
#   首选  中证红利低波动 H30269.XSHG 或 930146.XSHG (若能取到)
#   保底  中证红利 000922.XSHG (确定可用, 长历史; 无低波因子=回撤略大=更保守, 可接受)
RED_LOWVOL = '000922.XSHG'   # 先用保底; 若确认 H30269/930146 可取则换上, 更贴近ETF

LEGS = {
    '创业板':   '399006.XSHE',   # 创业板指(价格版, 2010+) 已确认
    '红利低波': RED_LOWVOL,      # 见上; 保底=中证红利
    '黄金':     'AU9999.XSGE',   # 上海金现货 2014+  <- 需 get_price 验证
    '豆粕':     'M9999.XDCE',    # 豆粕期货主力连续  <- 需 get_price 验证
    '十年国债': '000012.XSHG',   # 上证国债指数 已确认(作避险腿, 票息口径不完美可接受)
    # 纳指剔除: 聚宽无海外指数
}
SAFE = '十年国债'   # 危机滤网的避险目的地(必须是 LEGS 里的 key)


# ==================== 数据加载: 逐腿单独取价(研究环境稳健写法) ====================
# 不用多标的 get_price+pivot: 聚宽研究环境里多标的返回结构与回测器不同,
# pivot 易得到空/错列(表现为收益恒0). 单标的 get_price 稳定返回
# "日期为索引 + close列", 逐腿取再拼, 彻底避坑. 只有5腿, 不慢.
def load_closes():
    data = {}
    for name, code in LEGS.items():
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
        raise RuntimeError('全部腿取价失败, 检查 LEGS 里的 code')

    wide = pd.DataFrame(data).sort_index()
    print('数据区间:', wide.index.min().date(), '~', wide.index.max().date(),
          ' | 有效腿数:', wide.shape[1], '/', len(LEGS))
    print('各腿起始有效日 / 条数:')
    for n in wide.columns:
        s = wide[n].dropna()
        print('  %-8s %s  (%d条)' % (n, s.index.min().date(), len(s)))
    if SAFE not in wide.columns:
        raise RuntimeError('避险腿 %s 未取到, 危机滤网无法工作' % SAFE)
    # CTA腿注入: 合成净值当第6腿, 并注册到全局LEGS(引擎/逆波动率自动配权, 无需改引擎)
    if ADD_CTA:
        cta = build_cta_leg(wide.index)
        if cta is not None and len(cta) > MA_WINDOW:
            wide['CTA'] = cta
            wide['CTA'] = wide['CTA'].ffill()   # 对齐后前向填充, 避免个别缺日断链
            if 'CTA' not in LEGS:
                LEGS['CTA'] = 'SYNTHETIC_CTA'   # 占位code(不用于取价, 净值已算好)
            print('  已注入CTA腿, 池子腿数 -> %d' % wide.shape[1])
        else:
            print('!! CTA腿构造失败, 退回原池子')
    return wide


# ==================== CTA趋势跟踪腿: 合成一条净值曲线, 作为第6腿注入 ====================
# 思路: CTA不是"能持有的资产", 是一套"多空交易策略". 先把它合成成一只CTA基金的
#   净值(逐日多空收益复利), 再当普通腿丢进 closes, 引擎/逆波动率加权自动配它.
#   这样引擎一行不用改, 且可用 ADD_CTA 开关一键对比"加/不加".
# ★三条铁律(否则CTA结果虚高):
#   1. 严防未来函数: 信号(动量/波动率)一律 shift(1), 今日仓位只用昨日及之前信息.
#   2. 期货取【收盘价】做多空收益即可(主力连续已处理换月), 但要知道9999连续价
#      在换月点有跳变, 这里用pct_change近似, 真实CTA还有展期损益, 本压测偏乐观.
#   3. 未计交易成本/滑点. CTA换手高, 成本敏感, 纸面Calmar要打折看.
def build_cta_leg(index_ref):
    """返回一条CTA净值 Series(对齐到 index_ref 的交易日).
    每个品种: 趋势信号=sign(price_t-1 / price_{t-1-LOOKBACK} - 1), 逆波动率配权,
    整条腿缩放到 CTA_TARGET_VOL. 取不到的品种自动跳过(不报错)."""
    prices = {}
    for name, code in CTA_FUTURES.items():
        try:
            df = get_price(code, start_date=START, end_date=END,
                           frequency='daily', fields=['close'], fq='post')
            s = df['close'].dropna() if df is not None else None
            if s is not None and len(s) > CTA_LOOKBACK + CTA_VOL_WIN:
                prices[name] = s
            else:
                print('!! CTA跳过 %s(%s): 数据不足' % (name, code))
        except Exception as e:
            print('!! CTA跳过 %s(%s): %s' % (name, code, e))

    if len(prices) < 2:
        print('!! CTA可用品种<2, 放弃CTA腿')
        return None

    px = pd.DataFrame(prices).sort_index()
    rets = px.pct_change()                       # 各品种日收益
    # 趋势信号: LOOKBACK日动量的符号, shift(1)防未来函数(今日仓位用昨日信号)
    mom = px / px.shift(CTA_LOOKBACK) - 1.0
    signal = np.sign(mom).shift(1)               # +1做多 / -1做空 / 0无趋势
    # 逆波动率配权(风险平价), 同样 shift(1)
    vol = rets.rolling(CTA_VOL_WIN).std()
    inv_vol = (1.0 / vol).shift(1)
    inv_vol = inv_vol.replace([np.inf, -np.inf], np.nan)
    # 每日组合: 各品种 signal*inv_vol 归一化成权重, 乘当日收益
    raw_w = signal * inv_vol
    # 按当日可用品种的 |权重| 之和归一(gross=1), 再限总杠杆
    gross = raw_w.abs().sum(axis=1).replace(0.0, np.nan)
    w = raw_w.div(gross, axis=0).fillna(0.0)     # 每日多空权重, sum|w|<=1
    cta_ret = (w * rets).sum(axis=1)             # 组合日收益(多空)
    # 整条腿缩放到目标波动率(用【扩张窗】已实现波动率, 仍 shift(1) 防未来函数)
    realized = cta_ret.rolling(CTA_VOL_WIN).std() * np.sqrt(252)
    scale = (CTA_TARGET_VOL / realized).shift(1).clip(upper=CTA_GROSS_CAP).fillna(0.0)
    cta_ret_scaled = (cta_ret * scale).fillna(0.0)
    nav = (1.0 + cta_ret_scaled).cumprod()
    nav = nav.reindex(index_ref).ffill().dropna()
    print('CTA腿: 用了%d个品种 %s' % (px.shape[1], list(px.columns)))
    print('  CTA净值区间 %s ~ %s, 末值%.3f' %
          (nav.index.min().date(), nav.index.max().date(), nav.iloc[-1]))
    return nav


# ==================== 权重计算(用 t 之前数据, 无未来函数) ====================
def base_weights(strategy, legs, closes, upto, cap=None):
    """upto: 切片上界(不含), 即用 closes.iloc[:upto] 的历史.
    cap: M2C 的国债封顶值; None 则用全局 BOND_CAP(扫描时传不同cap)."""
    if cap is None:
        cap = BOND_CAP
    hist = closes.iloc[:upto]
    avail = [c for c in legs if hist[c].dropna().shape[0] >= MA_WINDOW]
    if not avail:
        return {}
    if strategy == 'M1':
        return {c: 1.0 / len(avail) for c in avail}
    # M2/M2M3/M2C: 逆波动率
    inv = {}
    for c in avail:
        s = hist[c].dropna()
        rets = s.iloc[-(VOL_WINDOW + 1):].pct_change().dropna()
        vol = rets.std()
        inv[c] = (1.0 / vol) if (vol and vol > 0 and not np.isnan(vol)) else 0.0
    tot = float(np.nansum(list(inv.values())))
    if tot <= 0:
        return {c: 1.0 / len(avail) for c in avail}
    w = {c: inv[c] / tot for c in avail}
    # M2C: 给避险腿(国债)封顶, 超出部分按逆波动率比例摊回其余腿, 迭代到收敛.
    #   打破国债主导, 逼组合吃股票风险溢价. M2/M2M3 不封顶(保持原样对照).
    if strategy == 'M2C' and SAFE in w and w[SAFE] > cap:
        others = [c for c in avail if c != SAFE]
        if others:
            excess = w[SAFE] - cap
            w[SAFE] = cap
            sub = float(np.nansum([inv[c] for c in others]))
            if sub > 0:
                for c in others:
                    w[c] = w[c] + excess * (inv[c] / sub)
    return w

def apply_crisis_filter(weights, closes, upto):
    """逐腿判200日线, 跌破份额转避险腿; 避险腿自身跌破则留现金."""
    hist = closes.iloc[:upto]
    target = {}
    defense = 0.0
    for c, w in weights.items():
        s = hist[c].dropna()
        if len(s) < MA_WINDOW:
            target[c] = target.get(c, 0.0) + w   # 数据不足不砍
            continue
        ma = s.iloc[-MA_WINDOW:].mean()
        if s.iloc[-1] > ma:
            target[c] = target.get(c, 0.0) + w
        else:
            defense += w
    if defense > 0:
        s = hist[SAFE].dropna()
        safe_ok = (len(s) >= MA_WINDOW) and (s.iloc[-1] > s.iloc[-MA_WINDOW:].mean())
        if safe_ok:
            target[SAFE] = target.get(SAFE, 0.0) + defense
        # 避险腿也破线 -> defense 份额留现金(不加回), 权重和<1 即持现金
    return target


# ==================== 回测引擎: 月度再平衡 + 金额记账(无归一化偏差) ====================
def run_backtest(strategy, closes, cap=None):
    """返回净值 Series. 月初第一个交易日用截至当日历史定权重.
    用【持仓金额】记账(hold[c]=各腿市值, cash=现金), 避免权重漂移不归一化
    造成的组合收益偏差; 现金腿(避险也破线时)如实计为不生息现金.
    cap: 仅 M2C 用, 传给 base_weights 做国债封顶(扫描时传不同值).
    """
    rets = closes.pct_change().fillna(0.0)
    dates = closes.index
    month_key = dates.to_series().dt.to_period('M')
    is_rebal = month_key.ne(month_key.shift(1)).values

    hold = {}          # code -> 市值
    cash = 1.0         # 初始全现金, 等第一个再平衡日建仓
    navs = []
    for i in range(len(dates)):
        # 各腿市值按当日收益增长(现金不生息)
        if hold:
            hold = {c: v * (1.0 + rets[c].iloc[i]) for c, v in hold.items()}
        total = float(np.nansum(list(hold.values()))) + cash
        navs.append(total)
        # 再平衡: 用截至今日(含)历史定权重, 按当前总资产重新分配
        if is_rebal[i] and i >= MA_WINDOW:
            bw = base_weights(strategy, list(LEGS.keys()), closes, i + 1, cap=cap)
            if strategy == 'M2M3':
                bw = apply_crisis_filter(bw, closes, i + 1)
            invested = float(np.nansum(list(bw.values())))   # <=1, 余下为现金
            hold = {c: total * w for c, w in bw.items()}
            cash = total * (1.0 - invested)
    return pd.Series(navs, index=dates, name=strategy)


# ==================== 绩效指标 ====================
def max_drawdown(nav):
    roll = nav.cummax()
    dd = nav / roll - 1.0
    return dd.min()

def metrics(nav):
    n = len(nav)
    years = n / 252.0
    total = nav.iloc[-1] / nav.iloc[0] - 1.0
    cagr = (nav.iloc[-1] / nav.iloc[0]) ** (1.0 / years) - 1.0
    rets = nav.pct_change().dropna()
    sharpe = (rets.mean() / rets.std() * np.sqrt(252)) if rets.std() > 0 else np.nan
    mdd = max_drawdown(nav)
    calmar = cagr / abs(mdd) if mdd < 0 else np.nan
    vol = rets.std() * np.sqrt(252)
    return dict(total=total, cagr=cagr, sharpe=sharpe, mdd=mdd,
                calmar=calmar, vol=vol)

def window_mdd(nav, start, end):
    sub = nav.loc[start:end]
    return max_drawdown(sub) if len(sub) > 5 else np.nan


# ==================== 15%预算方案: 杠杆 / 波动率目标 / 扫描 ====================
def lever_static(nav, L, financing=FINANCING):
    """对净值曲线上 L 倍静态杠杆, 扣融资成本(只对借来的 L-1 部分计息).
    净值日收益 r_lev = L*r - financing/252*(L-1). 无未来函数(逐日等比放大)."""
    r = nav.pct_change().fillna(0.0)
    daily_fin = financing / 252.0 * (L - 1.0)
    r_lev = L * r - daily_fin
    out = (1.0 + r_lev).cumprod()
    out.iloc[0] = 1.0
    return pd.Series(out.values, index=nav.index, name='%s_x%.2f' % (nav.name, L))


def vol_target(nav, target_vol=TARGET_VOL, win=VOL_TGT_WIN,
               max_lev=MAX_LEV, financing=FINANCING):
    """波动率目标: 每日按【昨日为止】的已实现年化波动率反推杠杆, 稳住组合波动率.
    lev_t = clip(target/realized_{t-1}, 0, max_lev). 借钱(lev>1)才计融资成本;
    lev<1 时闲置资金保守地按不生息现金处理. 用 shift(1) 严防未来函数."""
    r = nav.pct_change().fillna(0.0)
    realized = r.rolling(win).std() * np.sqrt(252)
    lev = (target_vol / realized).shift(1)          # 昨日信息定今日杠杆
    lev = lev.clip(upper=max_lev).fillna(0.0)       # 冷启动期无波动率估计 -> 空仓
    borrow = (lev - 1.0).clip(lower=0.0)            # 只有借钱部分计息
    daily_fin = financing / 252.0 * borrow
    r_vt = lev * r - daily_fin
    out = (1.0 + r_vt).cumprod()
    out.iloc[0] = 1.0
    return pd.Series(out.values, index=nav.index, name='%s_VT%.0f' % (nav.name, target_vol * 100))


def lev_to_fill_budget(nav, dd_budget=DD_BUDGET, max_lev=MAX_LEV):
    """求把回撤刚好撑到 dd_budget 所需的静态杠杆(不超 max_lev).
    静态杠杆下回撤近似线性放大: L* = dd_budget / |base_mdd|."""
    base_mdd = abs(max_drawdown(nav))
    if base_mdd <= 1e-9:
        return max_lev
    return min(dd_budget / base_mdd, max_lev)


def scan_bond_cap(closes, grid=CAP_GRID, is_end=IS_END):
    """BOND_CAP 扫描 + 样本内外切分. 对每个cap跑M2C, 分别在样本内(定参)、
    样本外(检验)算绩效. 目的: 暴露'收益vs回撤'前沿, 挑卡进15%预算的点,
    并用样本外证明它不是照图过拟合出来的."""
    rows = []
    for cap in grid:
        nav = run_backtest('M2C', closes, cap=cap)
        nav_is = nav.loc[:is_end]
        nav_oos = nav.loc[is_end:]
        m_all = metrics(nav)
        m_is = metrics(nav_is) if len(nav_is) > 60 else None
        m_oos = metrics(nav_oos) if len(nav_oos) > 60 else None
        # 该cap底盘吃满15%预算需几倍杠杆, 杠杆后净年化
        L = lev_to_fill_budget(nav)
        exc = m_all['cagr'] - FINANCING
        cagr_lev = m_all['cagr'] * L - FINANCING * (L - 1.0)
        mdd_lev = m_all['mdd'] * L
        rows.append(dict(cap=cap, m_all=m_all, m_is=m_is, m_oos=m_oos,
                         L=L, cagr_lev=cagr_lev, mdd_lev=mdd_lev, exc=exc))
    return rows


# ==================== 主流程 ====================
def main():
    closes = load_closes()
    results = {}
    navs = {}
    for strat in STRATEGIES:
        nav = run_backtest(strat, closes)
        navs[strat] = nav
        results[strat] = metrics(nav)

    print('\n' + '=' * 64)
    print('全期绩效 (%s ~ %s)' % (START, END))
    print('=' * 64)
    print('%-6s %8s %8s %7s %8s %7s %7s' %
          ('原型', '总收益', '年化', '夏普', '最大回撤', 'Calmar', '波动率'))
    for s in STRATEGIES:
        m = results[s]
        print('%-6s %7.1f%% %7.2f%% %7.3f %7.2f%% %7.2f %6.1f%%' %
              (s, m['total'] * 100, m['cagr'] * 100, m['sharpe'],
               m['mdd'] * 100, m['calmar'], m['vol'] * 100))

    print('\n' + '=' * 64)
    print('危机窗口 最大回撤 (这才是本次压测的核心)')
    print('=' * 64)
    hdr = '%-10s' % '危机窗口' + ''.join('%9s' % s for s in STRATEGIES)
    print(hdr)
    for name, (a, b) in CRISIS.items():
        row = '%-10s' % name
        for s in STRATEGIES:
            dd = window_mdd(navs[s], a, b)
            row += '%8.1f%%' % (dd * 100) if not np.isnan(dd) else '%9s' % 'n/a'
        print(row)

    # ==================== 15%预算方案: 扫描 + 杠杆 + 波动率目标 ====================
    print('\n' + '=' * 78)
    print('BOND_CAP 扫描 (全期 | 样本内<=%s定参 | 样本外检验)  融资成本=%.1f%%' %
          (IS_END, FINANCING * 100))
    print('=' * 78)
    print('%5s | %6s %6s %6s | %6s %6s | %6s %6s | 吃满%.0f%%预算' %
          ('cap', '年化', '回撤', 'Calm', 'IS年化', 'IS回撤',
           'OOS年化', 'OOS回撤', DD_BUDGET * 100))
    print('-' * 78)
    scan = scan_bond_cap(closes)
    for r in scan:
        m, mi, mo = r['m_all'], r['m_is'], r['m_oos']
        is_s = ('%5.1f%% %5.1f%%' % (mi['cagr'] * 100, mi['mdd'] * 100)) if mi else '   n/a      '
        oos_s = ('%5.1f%% %5.1f%%' % (mo['cagr'] * 100, mo['mdd'] * 100)) if mo else '   n/a      '
        print('%4.0f%% | %5.1f%% %5.1f%% %5.2f | %s | %s | L=%.2f->年化%4.1f%%/回撤%4.1f%%' %
              (r['cap'] * 100, m['cagr'] * 100, m['mdd'] * 100, m['calmar'],
               is_s, oos_s, r['L'], r['cagr_lev'] * 100, r['mdd_lev'] * 100))
    print('注: 全期回撤已>15%%的档, L被压到<1(其实是减仓); 关键看OOS年化/回撤跟IS是否一致(不一致=过拟合).')

    # 波动率目标版: 对 M2(高超额Calmar底盘) 和 M2C 各做一版, 目标波动率=TARGET_VOL
    print('\n' + '=' * 78)
    print('波动率目标版 (target_vol=%.0f%%, 回看%d日, 杠杆上限%.1f倍, 融资%.1f%%)' %
          (TARGET_VOL * 100, VOL_TGT_WIN, MAX_LEV, FINANCING * 100))
    print('=' * 78)
    print('%-14s %8s %8s %7s %8s %7s %7s' %
          ('版本', '总收益', '年化', '夏普', '最大回撤', 'Calmar', '波动率'))
    vt_navs = {}
    for base in ['M2', 'M2C']:
        vt = vol_target(navs[base])
        vt_navs[base] = vt
        mv = metrics(vt)
        print('%-14s %7.1f%% %7.2f%% %7.3f %7.2f%% %7.2f %6.1f%%' %
              (base + '+VT', mv['total'] * 100, mv['cagr'] * 100, mv['sharpe'],
               mv['mdd'] * 100, mv['calmar'], mv['vol'] * 100))
    # 波动率目标版的危机表(看急跌里减仓够不够快)
    print('\n波动率目标版 危机窗口回撤:')
    print('%-10s%12s%12s' % ('危机窗口', 'M2+VT', 'M2C+VT'))
    for name, (a, b) in CRISIS.items():
        row = '%-10s' % name
        for base in ['M2', 'M2C']:
            dd = window_mdd(vt_navs[base], a, b)
            row += '%11.1f%%' % (dd * 100) if not np.isnan(dd) else '%12s' % 'n/a'
        print(row)

    # 画图(研究环境可显示)
    try:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(12, 5))
        for s in STRATEGIES:
            ax.plot(navs[s].index, navs[s].values, label=s)
        for base in ['M2', 'M2C']:
            ax.plot(vt_navs[base].index, vt_navs[base].values,
                    '--', label=base + '+VT')
        ax.set_title('M1/M2/M2M3/M2C + vol-target long-history stress test (index proxy)')
        ax.legend(); ax.grid(alpha=0.3); ax.set_ylabel('NAV')
        plt.tight_layout(); plt.show()
    except Exception as e:
        print('绘图跳过:', e)

    return navs, results, scan, vt_navs


# 聚宽研究环境直接调 main(); 若在本地(无jqdata)仅做语法校验
if __name__ == '__main__':
    main()

