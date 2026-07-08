# -*- coding: utf-8 -*-
"""
ETF池子相关性检验 — 为"东升西落"跨资产轮动定池子
用新浪源抓不复权日线(相关性用日收益率算, 复权与否影响可忽略),
输出相关矩阵 + 各资产成立以来简单统计, 据此筛掉高相关冗余腿.
"""
import time, os
import akshare as ak
import pandas as pd, numpy as np

CAND = {
    "512890_红利低波":"sh512890",
    "510300_沪深300":"sh510300",
    "159915_创业板":"sz159915",
    "510500_中证500":"sh510500",
    "518880_黄金":"sh518880",
    "513100_纳指":"sh513100",
    "513500_标普500":"sh513500",
    "511260_十年国债":"sh511260",
}
os.makedirs("D:/Quant/data/pool", exist_ok=True)

def fetch(sym):
    fp = f"D:/Quant/data/pool/{sym}.csv"
    if os.path.exists(fp):
        d = pd.read_csv(fp)
        d['date'] = pd.to_datetime(d['date'])
        return d
    for i in range(5):
        try:
            d = ak.fund_etf_hist_sina(symbol=sym)
            d['date'] = pd.to_datetime(d['date'])
            d.to_csv(fp, index=False, encoding="utf-8-sig")
            return d
        except Exception as e:
            print(f"  {sym} retry{i}: {repr(e)[:45]}")
            time.sleep(3)
    return None

series = {}
for name, sym in CAND.items():
    d = fetch(sym)
    if d is not None and len(d) > 0:
        series[name] = d.set_index('date')['close'].rename(name)
        print(f"{name}: {d['date'].iloc[0].date()} ~ {d['date'].iloc[-1].date()} rows={len(d)}")
    else:
        print(f"{name}: FAILED")

if not series:
    raise SystemExit("no data")

px = pd.concat(series.values(), axis=1).sort_index()
# 全对齐的共同区间(最晚成立那只决定起点)
common = px.dropna()
print(f"\n[全体共同区间] {common.index[0].date()} ~ {common.index[-1].date()}  交易日 {len(common)}")

ret_all = px.pct_change()
print("\n=== 日收益相关矩阵(各自最长可用, 成对计算 pairwise) ===")
print(ret_all.corr().round(2).to_string())

print("\n=== 单资产统计(成立以来, 不复权价, 仅看波动/相关口径) ===")
for c in px.columns:
    s = px[c].dropna()
    r = s.pct_change().dropna()
    vol = r.std()*np.sqrt(252)
    print(f"{c:16s} rows {len(s):5d}  年化波动 {vol*100:5.1f}%")

# 保存宽表供后续回测/入池
px.to_csv("D:/Quant/data/pool/pool_close_wide.csv", encoding="utf-8-sig")
print("\nsaved D:/Quant/data/pool/pool_close_wide.csv")
