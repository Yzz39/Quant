# -*- coding: utf-8 -*-
"""
动量轮动"现实检验"回测 — 用本地真实ETF数据(qfq, 2015起)
目的: 验证"谁动量强切谁"是否水到渠成
核心实验:
  1. 相对动量轮动 (top-1/top-2, 月度) vs 买入持有沪深300
  2. 加入国债作绝对动量过滤 (双动量: 强者<0 或 <国债 则避险)
  3. 回看窗口敏感性 20/60/120/250 —— 证明过拟合风险
  4. 统计换手率/切换次数 —— 证明来回打脸成本
"""
import pandas as pd, numpy as np

WIDE = "D:/Quant/data/etf_momentum_close_wide_qfq.csv"
COST = 0.0002  # 单边万2(佣金+滑点近似), 切换换手时双边计

df = pd.read_csv(WIDE)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').set_index('date')

# 资产池: 行业+宽基做进攻, 国债做避险
BOND = '511260'   # 十年国债 (2017-08起)
BENCH = '510300'  # 沪深300 基准
# 进攻池: 行业ETF + 沪深300 + 创业板
OFFENSE = ['510300','159915','159928','512010','512400','512660',
           '512880','512980','512690','512800']

def perf(nav, label, extra=""):
    nav = nav.dropna()
    nav = nav / nav.iloc[0]
    yrs = (nav.index[-1]-nav.index[0]).days/365.25
    cagr = nav.iloc[-1]**(1/yrs)-1
    roll = nav.cummax()
    mdd = ((nav-roll)/roll).min()
    vol = nav.pct_change().std()*np.sqrt(252)
    calmar = cagr/abs(mdd) if mdd!=0 else np.nan
    print(f"{label:26s} CAGR {cagr*100:6.2f}%  MaxDD {mdd*100:7.1f}%  "
          f"Vol {vol*100:5.1f}%  Calmar {calmar:.2f}  {extra}")
    return dict(cagr=cagr,mdd=mdd,vol=vol,calmar=calmar)

def momentum_rotation(df, offense, bond, lookback, topn=1,
                      use_abs=True, start='2018-01-01'):
    """月度调仓: 取回看窗口涨幅排名前topn的进攻资产等权;
       若开启绝对动量且第一名动量<=国债动量(或<0) 则切国债避险."""
    px = df[offense+[bond]].copy()
    # 月末调仓日
    month_ends = px.resample('ME').last().index
    dates = px.index[px.index >= pd.Timestamp(start)]
    hold = {}          # {asset: shares}
    val = 1.0
    nav = pd.Series(index=dates, dtype=float)
    switches = 0
    turnover_sum = 0.0
    prev_targets = None
    px_ff = px.ffill()
    for i, d in enumerate(dates):
        # 先按当日价更新持仓市值
        if hold:
            v = sum(sh*px_ff.at[d,a] for a,sh in hold.items() if not np.isnan(px_ff.at[d,a]))
            if v>0: val = v
        nav.at[d] = val
        # 调仓日
        if d in set(month_ends):
            hist = px.loc[:d]
            if len(hist) <= lookback: 
                continue
            past = hist.iloc[-lookback-1]
            now = hist.iloc[-1]
            mom = (now/past - 1)
            bond_mom = mom[bond]
            cand = mom[offense].dropna().sort_values(ascending=False)
            if len(cand)==0:
                continue
            if use_abs and (cand.iloc[0] <= max(bond_mom, 0)):
                targets = [bond]           # 避险
            else:
                targets = list(cand.index[:topn])
            # 换手成本
            tset = set(targets)
            if prev_targets is not None and tset != set(prev_targets):
                switches += 1
                turnover_sum += 1.0
                val *= (1 - COST*2)        # 卖旧买新, 双边
            # 重新按等权建仓
            w = 1.0/len(targets)
            hold = {}
            for a in targets:
                p = px_ff.at[d,a]
                if not np.isnan(p):
                    hold[a] = (val*w)/p
            prev_targets = targets
    return nav.dropna(), switches

print("=== 基准: 买入持有 (2018-01起) ===")
bh = df[BENCH].loc['2018-01-01':]
perf(bh, "买入持有 沪深300")
bd = df[BOND].loc['2018-01-01':]
perf(bd, "买入持有 十年国债")

print("\n=== 实验3: 回看窗口敏感性 (相对动量 top1 + 双动量避险) ===")
for lb in [20,60,120,250]:
    nav,sw = momentum_rotation(df, OFFENSE, BOND, lookback=lb, topn=1, use_abs=True)
    perf(nav, f"动量轮动 lb={lb}d top1", extra=f"切换{sw}次")

print("\n=== 实验1: top1 vs top2 (lb=120, 双动量) ===")
for tn in [1,2,3]:
    nav,sw = momentum_rotation(df, OFFENSE, BOND, lookback=120, topn=tn, use_abs=True)
    perf(nav, f"动量轮动 lb=120 top{tn}", extra=f"切换{sw}次")

print("\n=== 实验2: 关掉绝对动量避险 (纯追强, lb=120 top1) ===")
nav,sw = momentum_rotation(df, OFFENSE, BOND, lookback=120, topn=1, use_abs=False)
perf(nav, "纯追强(无避险) lb=120", extra=f"切换{sw}次")
nav,sw = momentum_rotation(df, OFFENSE, BOND, lookback=120, topn=1, use_abs=True)
perf(nav, "双动量(带避险) lb=120", extra=f"切换{sw}次")
