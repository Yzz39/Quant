# -*- coding: utf-8 -*-
"""
扩池候选相关性检验 — 找能补"滞胀/过热/他国"象限的低相关腿
现有五腿: 红利低波 创业板 纳指 黄金 国债
新候选:   豆粕(农产品) 有色(工业金属) 恒生科技(港股) 日经(日本) 可转债
用日收益率相关矩阵筛: 与现有腿相关越低越有价值
"""
import time, os
import akshare as ak
import pandas as pd, numpy as np

# 现有池(已缓存) + 新候选
EXIST = {
    "红利低波":"sh512890","创业板":"sz159915","纳指":"sh513100",
    "黄金":"sh518880","国债":"sh511260",
}
NEW = {
    "豆粕":"sz159985","有色金属":"sh512400","恒生科技":"sh513180",
    "日经225":"sh513520","可转债":"sh511380","标普500":"sh513500",
}
base = "D:/Quant/data/pool"
os.makedirs(base, exist_ok=True)

def fetch(sym):
    fp = f"{base}/{sym}.csv"
    if os.path.exists(fp):
        d = pd.read_csv(fp); d['date']=pd.to_datetime(d['date']); return d
    for i in range(4):
        try:
            d = ak.fund_etf_hist_sina(symbol=sym)
            d['date']=pd.to_datetime(d['date'])
            d.to_csv(fp,index=False,encoding="utf-8-sig")
            return d
        except Exception as e:
            print(f"  {sym} retry{i}: {repr(e)[:40]}"); time.sleep(3)
    return None

series={}
allsyms={**EXIST,**NEW}
for name,sym in allsyms.items():
    d=fetch(sym)
    if d is not None and len(d)>0:
        series[name]=d.set_index('date')['close'].rename(name)
        print(f"{name:8s}({sym}): {d['date'].iloc[0].date()} ~ {d['date'].iloc[-1].date()} rows={len(d)}")
    else:
        print(f"{name:8s}({sym}): FAILED")

px=pd.concat(series.values(),axis=1).sort_index()
ret=px.pct_change()

print("\n=== 全体日收益相关矩阵(pairwise) ===")
print(ret.corr().round(2).to_string())

# 重点: 每个新候选 与 现有五腿 的平均绝对相关(越低越独立)
print("\n=== 新候选 vs 现有五腿 相关性(越低越值得进池) ===")
exist_names=[n for n in EXIST if n in ret.columns]
for n in NEW:
    if n not in ret.columns: 
        print(f"{n:8s}: 无数据"); continue
    cors={e: ret[n].corr(ret[e]) for e in exist_names}
    avg_abs=np.mean([abs(v) for v in cors.values() if not np.isnan(v)])
    detail=" ".join(f"{e}{cors[e]:+.2f}" for e in exist_names)
    print(f"{n:8s}: 平均|corr|={avg_abs:.2f}  | {detail}")
