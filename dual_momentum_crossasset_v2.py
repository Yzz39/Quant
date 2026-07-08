# -*- coding: utf-8 -*-
"""
跨资产双动量轮动 v2 — 用【后复权hfq】干净数据重跑
先做数据校验: 红利低波须回到 ~+11%/-16.5% 才算数据修对
"""
import pandas as pd, numpy as np, os

base = "D:/Quant/data/pool_hfq"
POOL = {"512890":"红利低波","159915":"创业板","513100":"纳指",
        "518880":"黄金","159985":"豆粕","511260":"国债"}
OFFENSE=["红利低波","创业板","纳指","黄金","豆粕"]
BOND="国债"
COST=0.0001

def load():
    s={}
    for code,name in POOL.items():
        d=pd.read_csv(f"{base}/{code}.csv")
        d.columns=['date','open','close','high','low','vol','amt','amp','pct','chg','turn'][:len(d.columns)]
        d['date']=pd.to_datetime(d['date'])
        s[name]=d.set_index('date')['close'].rename(name)
    return pd.concat(s.values(),axis=1,sort=True).sort_index()

def perf(nav,label):
    nav=nav.dropna(); nav=nav/nav.iloc[0]
    yrs=(nav.index[-1]-nav.index[0]).days/365.25
    cagr=nav.iloc[-1]**(1/yrs)-1
    roll=nav.cummax(); mdd=((nav-roll)/roll).min()
    vol=nav.pct_change().std()*np.sqrt(252)
    cal=cagr/abs(mdd) if mdd!=0 else np.nan
    print(f"{label:30s} CAGR {cagr*100:6.2f}%  MaxDD {mdd*100:7.1f}%  Vol {vol*100:5.1f}%  Calmar {cal:.2f}")
    return dict(cagr=cagr,mdd=mdd,cal=cal)

def dual_momentum(px,L,K,start):
    px=px.ffill()
    me=px.resample('ME').last().index
    dates=px.index[px.index>=pd.Timestamp(start)]
    hold={}; val=1.0; prev=None; nav=pd.Series(index=dates,dtype=float); sw=0
    for d in dates:
        if hold: val=sum(sh*px.at[d,a] for a,sh in hold.items())
        nav.at[d]=val
        if d in set(me):
            hist=px.loc[:d]
            if len(hist)<=L: continue
            mom=hist.iloc[-1]/hist.iloc[-L-1]-1
            cand=mom[OFFENSE].dropna().sort_values(ascending=False)
            picked=[a for a in cand.index[:K] if cand[a]>0]
            nb=K-len(picked); tg={}; w=1.0/K
            for a in picked: tg[a]=w
            if nb>0: tg[BOND]=tg.get(BOND,0)+w*nb
            if prev is None or set(tg)!=set(prev) or \
               any(abs(tg.get(k,0)-prev.get(k,0))>1e-9 for k in set(tg)|set(prev)):
                sw+=1; val*=(1-COST*2)
            hold={a:(val*wt)/px.at[d,a] for a,wt in tg.items()}
            prev=tg
    return nav.dropna(),sw

px=load()
print("各腿数据范围:")
for c in px.columns:
    s=px[c].dropna()
    print(f"  {c:8s} {s.index[0].date()} ~ {s.index[-1].date()} n={len(s)}")

# 数据校验: 红利低波 2019-01-18 起 应≈ +11.36%/-16.5%
print("\n[数据校验] 红利低波(应≈CAGR11.4%/MDD-16.5%):")
perf(px["红利低波"].loc["2019-01-18":],"  红利低波 hfq 2019起")

start=px.dropna().index[0]
print(f"\n6腿共同起点: {start.date()} (受豆粕约束)\n=== 基准 ===")
perf(px["红利低波"].loc[start:],"买入持有 红利低波")
perf(px["创业板"].loc[start:],"买入持有 创业板")
eq=(px[OFFENSE+[BOND]].loc[start:].pct_change().fillna(0).mean(axis=1)+1).cumprod()
perf(eq,"六腿等权(不轮动)")

print("\n=== 双动量轮动 v2 (L=120,K=2) ===")
nav,sw=dual_momentum(px,120,2,start)
perf(nav,"双动量 L120 K2"); print(f"  切换 {sw} 次")
