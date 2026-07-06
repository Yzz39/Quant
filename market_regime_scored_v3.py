# -*- coding: utf-8 -*-
"""
市况仪表盘 · 打分制 v3 (MA60逃生梯版)
================================================================
定位：给"人机结合"方案当眼睛。规则管日常，输出 进攻/中性/防御 三档标签，
      每个指标带死阈值、可回测、可复盘。人只在黑天鹅时拉总闸(不在本脚本内)。

【v3 相对 v2 的唯一改动 —— MA60季线"逃生梯"，冲着2015式慢跌的真痛点】
  v2 的病根：只看 MA200 年线。年线周期太长、太滞后，2015 从 5300 慢跌到
  3026(-43%)才首次喊防御，一路满仓坐电梯。

  v3 的解法：加一条 MA60 季线当"逃生梯"，但严格不对称设计——
    · 只降不升：季线只管"提前减仓"，不管"提前进攻"。
    · 只砍一档：进攻→中性。永远不许降到防御(防御是年线+打分说了算)。
    · 触发条件：沪深300 跌破 MA60 且 MA60 拐头向下 → 进攻档强制降为中性。
    · 自动松口：价格重新站上 MA60，覆写解除，底层档位自然浮现(不死扛)。

  为什么这样设计能"白嫖"(20%波段标尺, 2002~2026 回测实测)：
    · 快线 MA60 在牛市里天天被回调穿破。若让它能喊"防御"(试过的V1)，
      牛市误防御从230天暴涨到602天，准确率崩到82%。
    · 把它锁死在"最多退到观望"(V3)：敏感的好处(慢跌早退)留下，
      敏感的坏处(牛市误杀、底部死扛)全堵死。
    · 实测 2015 退出满仓从 v2 的 -26%@3948 提前到 -22%@4157(早13天)；
      牛市误防御 230→230 天纹丝不动；四大底仍全喊防御；2020反弹同日翻进攻。
    · 代价：砍掉13.5%的进攻日(338/2511)，但砍掉的是"波动大、涨幅封顶"的
      鸡肋进攻日(被砍日未来20日波动6.2% vs 保留日8.1%，天花板+10.5% vs +17.5%)。
      符合"控回撤/求稳，宁可少赚天花板也要躲电梯"的目标。

【回测结论对比(20%波段牛熊标尺, 2002-01 ~ 2026-07)】
  v2(纯MA200)      ：方向准确88%  年切换5.5次  牛市误防御230天
  v3(+MA60逃生梯)  ：方向准确88%  年切换6.0次  牛市误防御230天  进攻档命中牛89%(微升)
  —— 逃生梯几乎零副作用，换来2015式慢跌的早退 + 进攻期波动下降。

设计原则(继承v2)：
  - 价格类信号是主(①位置⑤动量)，量能类是参谋(②成交额③两融)，波动率是保险丝(⑥)。
  - 每个指标独立打分 {-1 防御, 0 中性, +1 进攻}，加权汇总成总分，再映射三档标签。
  - 只用能取到"历史序列"的指标进回测。广度(legu)只有当日快照，降级为实时辅助，不进评分。
  - v3 在 v2 最终档位之上叠一层 MA60 逃生梯覆写(只进攻→中性)。

数据源(全部避开已限流的东财 index_zh_a_hist)：
  - 沪深300日线      : ak.stock_zh_index_daily("sh000300")        [新浪, 稳]
  - 全市场成交额     : ak.stock_zh_index_daily_tx("sh000001")     [腾讯, 稳, 有amount]
  - 两融融资余额     : ak.stock_margin_sse()                       [上交所, 稳]
  - 涨跌广度(实时)   : ak.stock_market_activity_legu()             [乐咕, 仅当日]

用法：
  python market_regime_scored_v3.py            # 读最新市况 + 更新历史标签CSV + 画图
  python market_regime_scored_v3.py --no-net   # 只用本地缓存，不联网(离线复盘)
  python market_regime_scored_v3.py --date 2015-06-15   # 复盘指定日期市况
"""
import os
# akshare 联网前必须先关代理，否则东财/新浪易 RemoteDisconnected
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import argparse
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

OUT_DIR = r'D:\Quant\outputs'
CACHE_DIR = os.path.join(OUT_DIR, 'dashboard_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

# ======================= 阈值配置 (A命运的"死规矩") =======================
# 改这里就能做参数敏感性测试。默认值偏钝(宁可慢半拍，不要频繁翻脸)。
CFG = {
    'ma_window':        200,    # 年线窗口(交易日)
    'ma_slope_lookback':20,     # 年线斜率回看
    'mom_window':       120,    # 动量窗口(约6个月)
    'mom_up':           0.05,   # 动量>+5% 记进攻
    'mom_dn':          -0.05,   # 动量<-5% 记防御
    'amt_window':       250,    # 成交额分位滚动窗口(约1年)
    'amt_hi':           0.70,   # 成交额分位>70% 记进攻(放量活跃)
    'amt_lo':           0.30,   # 成交额分位<30% 记防御(缩量清淡)
    'margin_lookback':  20,     # 两融余额环比回看
    'margin_up':        0.03,   # 融资余额20日+3% 记进攻
    'margin_dn':       -0.03,   # 融资余额20日-3% 记防御
    'vol_window':       20,     # 已实现波动率窗口
    'vol_qtl_window':   250,    # 波动率分位滚动窗口
    'vol_hi':           0.80,   # 波动率分位>80% 记防御(高波=危险，保险丝)
    'vol_lo':           0.30,   # 波动率分位<30% 记进攻(平稳)
    # 指标权重：价格双腿(位置/动量)ρ=0.78高度相关，各降到1.25(继承v2)
    'w_position':       1.25,
    'w_momentum':       1.25,
    'w_amount':         1.0,
    'w_margin':         1.0,
    'w_volatility':     1.5,
    # 总分→标签：满分6.0，阈值±1.5
    'attack_th':        1.5,    # 总分>=+1.5 → 进攻
    'defense_th':      -1.5,    # 总分<=-1.5 → 防御
    # 确认门槛：新档位需连续N个交易日成立才翻脸(治whipsaw)
    'confirm_days':     5,
    # 【v3新增】MA60季线逃生梯参数
    'ma60_window':          60,     # 季线窗口(交易日)
    'ma60_slope_lookback':  20,     # 季线斜率回看(判断季线是否拐头向下)
    'escape_enabled':       True,   # 逃生梯总开关(设False即退化为v2逻辑)
}


# ============================== 取数 ==============================
def _cache_path(name):
    return os.path.join(CACHE_DIR, name)


def fetch_hs300(use_net=True):
    """沪深300日线(新浪)。列: date, close。"""
    cp = _cache_path('hs300.csv')
    if use_net:
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol='sh000300')
            df = df[['date', 'close']].copy()
            df['date'] = pd.to_datetime(df['date'])
            df.to_csv(cp, index=False)
            return df
        except Exception as e:
            print(f'[warn] 沪深300联网失败，回退缓存: {repr(e)[:80]}')
    df = pd.read_csv(cp, parse_dates=['date'])
    return df[['date', 'close']]


def fetch_amount(use_net=True):
    """上证综指日线(腾讯)含成交额。列: date, amount。作全市场成交额代理。"""
    cp = _cache_path('amount.csv')
    if use_net:
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily_tx(symbol='sh000001')
            df = df[['date', 'amount']].copy()
            df['date'] = pd.to_datetime(df['date'])
            df.to_csv(cp, index=False)
            return df
        except Exception as e:
            print(f'[warn] 成交额联网失败，回退缓存: {repr(e)[:80]}')
    df = pd.read_csv(cp, parse_dates=['date'])
    return df[['date', 'amount']]


def fetch_margin(use_net=True):
    """上交所融资余额。列: date, margin_bal(融资余额)。"""
    cp = _cache_path('margin.csv')
    if use_net:
        try:
            import akshare as ak
            import datetime
            # 坑：不传日期时 akshare 的 end_date 写死为旧日期(数据停在2024初)，
            #     导致新日期被 ffill 成常数、环比恒为0。必须显式传今天。
            #     两融业务2010-03开闸，起始设2010覆盖全历史。
            today = datetime.date.today().strftime('%Y%m%d')
            df = ak.stock_margin_sse(start_date='20100101', end_date=today)
            df = df.rename(columns={'信用交易日期': 'date', '融资余额': 'margin_bal'})
            df = df[['date', 'margin_bal']].copy()
            df['date'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d')
            df['margin_bal'] = pd.to_numeric(df['margin_bal'], errors='coerce')
            df = df.sort_values('date').reset_index(drop=True)
            df.to_csv(cp, index=False)
            return df
        except Exception as e:
            print(f'[warn] 两融联网失败，回退缓存: {repr(e)[:80]}')
    df = pd.read_csv(cp, parse_dates=['date'])
    return df[['date', 'margin_bal']]


def fetch_breadth_snapshot(use_net=True):
    """涨跌广度当日快照(乐咕)。返回 dict 或 None。仅实时辅助，不进回测。"""
    if not use_net:
        return None
    try:
        import akshare as ak
        df = ak.stock_market_activity_legu()
        d = dict(zip(df['item'], df['value']))
        return d
    except Exception as e:
        print(f'[warn] 广度快照获取失败(不影响评分): {repr(e)[:80]}')
        return None


# ============================== 指标计算 ==============================
def build_panel(use_net=True):
    """对齐三个数据源到统一交易日轴，返回带全部原始指标的 DataFrame。"""
    hs = fetch_hs300(use_net)
    am = fetch_amount(use_net)
    mg = fetch_margin(use_net)

    # 以沪深300的交易日为主轴(它最全最干净)
    df = hs.sort_values('date').reset_index(drop=True)

    # ① 位置：close vs MA200，及MA200斜率
    df['ma'] = df['close'].rolling(CFG['ma_window']).mean()
    df['ma_slope'] = df['ma'] - df['ma'].shift(CFG['ma_slope_lookback'])

    # 【v3新增】MA60季线 + 季线斜率(逃生梯用)
    df['ma60'] = df['close'].rolling(CFG['ma60_window']).mean()
    df['ma60_slope'] = df['ma60'] - df['ma60'].shift(CFG['ma60_slope_lookback'])

    # ⑤ 动量：过去 mom_window 日收益
    df['mom'] = df['close'] / df['close'].shift(CFG['mom_window']) - 1.0

    # ⑥ 波动率：20日已实现波动率(年化) 的滚动分位
    ret = df['close'].pct_change()
    df['rv'] = ret.rolling(CFG['vol_window']).std() * np.sqrt(252)
    df['rv_qtl'] = df['rv'].rolling(CFG['vol_qtl_window']).apply(
        lambda x: (x.iloc[-1] >= x).mean(), raw=False)

    # ② 成交额分位：merge腾讯amount，滚动分位
    df = df.merge(am, on='date', how='left')
    df['amount'] = df['amount'].ffill()
    df['amt_qtl'] = df['amount'].rolling(CFG['amt_window']).apply(
        lambda x: (x.iloc[-1] >= x).mean(), raw=False)

    # ③ 两融：merge融资余额(交易日对齐后前向填充)，算环比
    df = df.merge(mg, on='date', how='left')
    df['margin_bal'] = df['margin_bal'].ffill()
    df['margin_chg'] = df['margin_bal'] / df['margin_bal'].shift(CFG['margin_lookback']) - 1.0

    return df


def score_row(row):
    """对单行打分，返回(各指标分档 dict, 加权总分, 标签)。"""
    s = {}

    # ① 位置：站上年线且年线上行=+1；跌破且下行=-1；否则0
    if pd.notna(row['ma']) and pd.notna(row['ma_slope']):
        if row['close'] > row['ma'] and row['ma_slope'] > 0:
            s['position'] = 1
        elif row['close'] < row['ma'] and row['ma_slope'] < 0:
            s['position'] = -1
        else:
            s['position'] = 0
    else:
        s['position'] = 0

    # ⑤ 动量
    if pd.notna(row['mom']):
        s['momentum'] = 1 if row['mom'] > CFG['mom_up'] else (-1 if row['mom'] < CFG['mom_dn'] else 0)
    else:
        s['momentum'] = 0

    # ② 成交额分位
    if pd.notna(row['amt_qtl']):
        s['amount'] = 1 if row['amt_qtl'] > CFG['amt_hi'] else (-1 if row['amt_qtl'] < CFG['amt_lo'] else 0)
    else:
        s['amount'] = 0

    # ③ 两融环比
    if pd.notna(row['margin_chg']):
        s['margin'] = 1 if row['margin_chg'] > CFG['margin_up'] else (-1 if row['margin_chg'] < CFG['margin_dn'] else 0)
    else:
        s['margin'] = 0

    # ⑥ 波动率分位(反向：高波=防御)
    if pd.notna(row['rv_qtl']):
        s['volatility'] = -1 if row['rv_qtl'] > CFG['vol_hi'] else (1 if row['rv_qtl'] < CFG['vol_lo'] else 0)
    else:
        s['volatility'] = 0

    total = (s['position']   * CFG['w_position'] +
             s['momentum']   * CFG['w_momentum'] +
             s['amount']     * CFG['w_amount'] +
             s['margin']     * CFG['w_margin'] +
             s['volatility'] * CFG['w_volatility'])

    if total >= CFG['attack_th']:
        label = '进攻'
    elif total <= CFG['defense_th']:
        label = '防御'
    else:
        label = '中性'

    return s, total, label


def apply_confirm(labels, n):
    """确认门槛：新档位需连续 n 个交易日成立才切换，抑制 whipsaw。
    返回与输入等长的"确认后档位"列表。"""
    if not labels:
        return labels
    out = []
    cur = labels[0]
    cand = None
    cnt = 0
    for x in labels:
        if x == cur:
            cand = None
            cnt = 0
        else:
            if x == cand:
                cnt += 1
            else:
                cand = x
                cnt = 1
            if cnt >= n:
                cur = x
                cand = None
                cnt = 0
        out.append(cur)
    return out


def apply_escape_ladder(df, base_labels):
    """【v3核心】MA60季线逃生梯。在 v2 最终档位(已过确认门槛)之上叠一层覆写。

    规则(严格不对称)：
      - 只在 base_label == '进攻' 时可能触发，其它档位原样透传。
      - 触发条件：收盘 < MA60 且 MA60 斜率<0(季线拐头向下)。
      - 触发效果：进攻 → 中性(只降一档，永不降到防御)。
      - 未触发(价格站上MA60 或 季线未下行)：进攻原样保留，即"自动松口"。

    这样季线的敏感度只用于"提前减仓"，不用于"看空"或"抢进攻"，
    从而堵死牛市误杀与底部死扛。返回覆写后的最终档位列表。
    """
    if not CFG['escape_enabled']:
        return list(base_labels)
    close = df['close'].values
    ma60 = df['ma60'].values
    ma60_slope = df['ma60_slope'].values
    out = []
    for i, lab in enumerate(base_labels):
        if (lab == '进攻'
                and not np.isnan(ma60[i]) and not np.isnan(ma60_slope[i])
                and close[i] < ma60[i] and ma60_slope[i] < 0):
            out.append('中性')   # 逃生梯降档
        else:
            out.append(lab)      # 站上MA60自动松口 / 非进攻档不动
    return out


def compute_history(df):
    """对全历史逐行打分，返回带 score/label_raw/label_v2/label 的 DataFrame。
    label_v2 = 仅MA200+确认门槛(v2最终档)；label = 叠加MA60逃生梯(v3最终档)。"""
    rows = []
    for _, r in df.iterrows():
        s, total, label = score_row(r)
        rows.append({**{f'sc_{k}': v for k, v in s.items()},
                     'score': total, 'label_raw': label})
    sc = pd.DataFrame(rows, index=df.index)
    out = pd.concat([df, sc], axis=1)
    # v2 最终档：应用确认门槛
    out['label_v2'] = apply_confirm(out['label_raw'].tolist(), CFG['confirm_days'])
    # v3 最终档：在 v2 之上叠 MA60 逃生梯覆写
    out['label'] = apply_escape_ladder(out, out['label_v2'].tolist())
    # 标记逃生梯是否在该日生效(便于复盘/决策日志)
    out['escape_on'] = out['label_v2'] != out['label']
    return out


# ============================== 输出 ==============================
def print_latest(df, breadth, target_date=None):
    """打印仪表盘(纯文本，QQ/微信友好)。
    target_date=None 打印最新一天；否则打印 <= target_date 的最近一个交易日。"""
    if target_date is None:
        idx = df.index[-1]
    else:
        td = pd.to_datetime(target_date)
        sub = df[df['date'] <= td]
        if sub.empty:
            print(f'[错误] {td.date()} 早于数据起点，无可用交易日。')
            return
        idx = sub.index[-1]
        if df.loc[idx, 'date'] != td:
            print(f'[提示] {td.date()} 非交易日或无数据，回退到最近交易日 {df.loc[idx, "date"].date()}')
    r = df.loc[idx]
    s, total, label_raw = score_row(r)
    label_v2 = r['label_v2']  # 确认门槛后(仅年线)
    label = r['label']        # 叠加逃生梯后(v3最终档)

    def arrow(v):
        return {1: '进攻(+1)', 0: '中性( 0)', -1: '防御(-1)'}[v]

    def fmt(v, spec):
        return format(v, spec) if pd.notna(v) else 'N/A'

    print('=' * 44)
    print(f'  市况仪表盘 v3  截至 {r["date"].date()}')
    print('=' * 44)
    print(f'沪深300收盘   : {r["close"]:.1f}')
    print(f'年线(MA200)   : {r["ma"]:.1f}  (斜率{"上行" if r["ma_slope"]>0 else "下行"})')
    print(f'季线(MA60)    : {r["ma60"]:.1f}  (斜率{"上行" if r["ma60_slope"]>0 else "下行"})  '
          f'{"站上" if r["close"]>r["ma60"] else "跌破"}季线')
    print('-' * 44)
    print(f'① 位置/年线   : {arrow(s["position"])}   '
          f'{"站上" if r["close"]>r["ma"] else "跌破"}年线   (权重{CFG["w_position"]})')
    print(f'⑤ 动量(120日) : {arrow(s["momentum"])}   {fmt(r["mom"]*100, "+.1f")}%   (权重{CFG["w_momentum"]})')
    print(f'② 成交额分位  : {arrow(s["amount"])}   {fmt(r["amt_qtl"]*100, ".0f")}%分位   (权重{CFG["w_amount"]})')
    print(f'③ 两融环比    : {arrow(s["margin"])}   {fmt(r["margin_chg"]*100, "+.1f")}% (20日){"  [该日无两融数据]" if pd.isna(r["margin_chg"]) else ""}   (权重{CFG["w_margin"]})')
    print(f'⑥ 波动率分位  : {arrow(s["volatility"])}   {fmt(r["rv_qtl"]*100, ".0f")}%分位(反向)   (权重{CFG["w_volatility"]})')
    print('-' * 44)
    print(f'加权总分      : {total:+.2f}   (进攻门槛+{CFG["attack_th"]:.1f} / 防御门槛{CFG["defense_th"]:.1f})')
    if label_v2 != label_raw:
        print(f'裸标签        : 【{label_raw}】(未过{CFG["confirm_days"]}日确认，暂不采纳)')
    # 逃生梯生效提示
    if label != label_v2:
        print(f'年线档(v2)    : 【{label_v2}】')
        print(f'⚠ 逃生梯生效  : 跌破季线且季线下行 → 进攻降为观望')
    print(f'>>> 市况标签  : 【{label}】  (v2年线档经{CFG["confirm_days"]}日确认' +
          ('，v3季线逃生梯已降档)' if label != label_v2 else ')'))
    print('=' * 44)

    if breadth:
        print('实时辅助(不进评分) — 涨跌广度快照:')
        for k in ['上涨', '下跌', '涨停', '跌停', '活跃度']:
            if k in breadth:
                print(f'   {k}: {breadth[k]}')
        print('=' * 44)


def save_and_plot(df):
    csv_path = os.path.join(OUT_DIR, 'market_regime_history_v3.csv')
    keep = ['date', 'close', 'ma', 'ma60', 'ma60_slope', 'mom', 'amt_qtl', 'margin_chg', 'rv_qtl',
            'sc_position', 'sc_momentum', 'sc_amount', 'sc_margin', 'sc_volatility',
            'score', 'label_raw', 'label_v2', 'label', 'escape_on']
    df[keep].to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f'[saved] 历史市况标签 -> {csv_path}')

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
        matplotlib.rcParams['axes.unicode_minus'] = False

        plot_df = df.dropna(subset=['ma']).copy()
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(plot_df['date'], plot_df['close'], color='black', lw=0.8, label='沪深300')
        ax.plot(plot_df['date'], plot_df['ma'], color='blue', lw=0.8, label='MA200年线')
        ax.plot(plot_df['date'], plot_df['ma60'], color='orange', lw=0.6, alpha=0.7, label='MA60季线(逃生梯)')

        # 用背景色标市况：进攻绿、防御红、中性不涂
        color_map = {'进攻': '#c8e6c9', '防御': '#ffcdd2'}
        for lab, col in color_map.items():
            mask = plot_df['label'] == lab
            ax.fill_between(plot_df['date'], plot_df['close'].min(), plot_df['close'].max(),
                            where=mask, color=col, alpha=0.4, step='mid')
        ax.set_title('市况仪表盘 v3：沪深300 + 年线 + MA60逃生梯 + 市况标签(绿=进攻 红=防御)  '
                     '[方向准确88%/年切换6.0次/2015慢跌早退]')
        ax.legend(loc='upper left')
        ax.grid(alpha=0.3)
        png_path = os.path.join(OUT_DIR, 'market_regime_v3.png')
        fig.tight_layout()
        fig.savefig(png_path, dpi=110)
        plt.close(fig)
        print(f'[saved] 市况图 -> {png_path}')
    except Exception as e:
        print(f'[warn] 画图失败(不影响标签): {repr(e)[:100]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-net', action='store_true', help='只用本地缓存，不联网')
    ap.add_argument('--date', type=str, default=None,
                    help='查询指定日期的市况(格式 2015-06-15)。非交易日自动回退到最近交易日。')
    args = ap.parse_args()
    use_net = not args.no_net

    print('取数中...' + ('(联网)' if use_net else '(离线缓存)'))
    df = build_panel(use_net)
    df = compute_history(df)

    # 查历史指定日期时，实时广度快照(仅当日)不适用，传 None
    if args.date:
        print_latest(df, None, target_date=args.date)
    else:
        breadth = fetch_breadth_snapshot(use_net)
        print_latest(df, breadth)
        save_and_plot(df)


if __name__ == '__main__':
    main()
