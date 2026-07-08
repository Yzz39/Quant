# -*- coding: utf-8 -*-
"""
跨资产双动量轮动 v1 — 本地样本外验证
池子6腿: 红利低波/创业板/纳指/黄金/豆粕(进攻) + 十年国债(避险)
机制:
  - 相对动量: 月末按过去L日涨幅给5个进攻腿排名
  - 绝对动量避险: 进最终持仓须 (排名前K) 且 (过去L日涨幅>0);
                  合格腿不足K个, 空出仓位切国债
  - 等权持有, 月度调仓, 成本单边万1+双边滑点
对照基准: 买入持有红利低波 / 买入持有沪深300 / 六腿等权不轮动
"""
import pandas as pd, numpy as np, os

base = "D:/Quant/data/pool"
LEGS = {  # sina symbol
    "红利低波":"sh512890","创业板":"sz159915","纳指":"sh513100",
    "黄金":"sh518880","豆粕":"sz159985","国债":"sh511260",
}
OFFENSE = ["红利低波","创业板","纳指","黄金","豆粕"]
BOND = "国债"
COST = 0.0001  # 单边万1

def load():
    s={}
    for name,sym in LEGS.items():
        d=pd.read_csv(f"{base}/{sym}.csv"); d['date']=pd.to_datetime(d['date'])
        s[name]=d.set_index('date')['close'].rename(name)
    px=pd.concat(s.values(),axis=1).sort_index()
    return px

def perf(nav,label):
    nav=nav.dropna(); nav=nav/nav.iloc[0]
    yrs=(nav.index[-1]-nav.index[0]).days/365.25
    cagr=nav.iloc[-1]**(1/yrs)-1
    roll=nav.cummax(); mdd=((nav-roll)/roll).min()
    vol=nav.pct_change().std()*np.sqrt(252)
    calmar=cagr/abs(mdd) if mdd!=0 else np.nan
    print(f"{label:30s} CAGR {cagr*100:6.2f}%  MaxDD {mdd*100:7.1f}%  Vol {vol*100:5.1f}%  Calmar {calmar:.2f}")
    return dict(cagr=cagr,mdd=mdd,calmar=calmar)

def dual_momentum(px, L, K, start):
    px=px.ffill()
    offense=OFFENSE; bond=BOND
    month_ends=px.resample('ME').last().index
    dates=px.index[px.index>=pd.Timestamp(start)]
    hold={}; val=1.0; prev=None
    nav=pd.Series(index=dates,dtype=float)
    daily=px.pct_change().fillna(0)
    switches=0
    for d in dates:
        if hold:
            val=sum(sh*px.at[d,a] for a,sh in hold.items())
        nav.at[d]=val
        if d in set(month_ends):
            hist=px.loc[:d]
            if len(hist)<=L: continue
            mom=hist.iloc[-1]/hist.iloc[-L-1]-1
            cand=mom[offense].dropna().sort_values(ascending=False)
            # 排名前K 且 绝对动量>0
            picked=[a for a in cand.index[:K] if cand[a]>0]
            n_bond=K-len(picked)  # 空出的切国债
            targets={}
            w=1.0/K
            for a in picked: targets[a]=w
            if n_bond>0: targets[bond]=targets.get(bond,0)+w*n_bond
            if prev is None or set(targets)!=set(prev) or \
               any(abs(targets.get(k,0)-prev.get(k,0))>1e-9 for k in set(targets)|set(prev)):
                switches+=1
                val*=(1-COST*2)
            hold={a:(val*wt)/px.at[d,a] for a,wt in targets.items()}
            prev=targets
    return nav.dropna(), switches

px=load()
print("数据区间:", px.dropna().index[0].date(),"~",px.dropna().index[-1].date())
print("(豆粕2019-12才有, 共同起点受它约束)\n")

# 共同起点
start=px.dropna().index[0]
print("=== 基准 ===")
perf(px["红利低波"].loc[start:],"买入持有 红利低波")
perf(px["创业板"].loc[start:],"买入持有 创业板")
eq=(px[OFFENSE+[BOND]].loc[start:].pct_change().fillna(0).mean(axis=1)+1).cumprod()
perf(eq,"六腿等权(不轮动)")

print("\n=== 双动量轮动 v1 (L=120, K=2) ===")
nav,sw=dual_momentum(px,120,2,start)
perf(nav,"双动量 L120 K2")
print(f"  调仓切换次数: {sw}")
