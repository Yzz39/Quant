# -*- coding: utf-8 -*-
"""
前视偏差检验: 用 2019 年之前(2014-2018)的数据算相关矩阵,
看"低相关结构"是不是 2019 年初就已经可见 —— 若是, 则池子选择
靠的是【结构】(ex-ante 可得), 而非【未来收益】(hindsight).

对照: 2014-2018(样本外/决策前) vs 2019-2026(用户观察期)
"""
import pandas as pd, numpy as np, os

FILES = {
    "沪深300":"sh510300",
    "创业板":"sz159915",
    "中证500":"sh510500",
    "黄金":"sh518880",
    "纳指":"sh513100",
    "标普500":"sh513500",
    "十年国债":"sh511260",   # 2017-08 才有, 只能覆盖 2017-2018
}
base = "D:/Quant/data/pool"
series = {}
for name, sym in FILES.items():
    fp = f"{base}/{sym}.csv"
    if not os.path.exists(fp):
        print(f"{name}: file missing"); continue
    d = pd.read_csv(fp); d['date'] = pd.to_datetime(d['date'])
    series[name] = d.set_index('date')['close'].rename(name)

px = pd.concat(series.values(), axis=1).sort_index()
ret = px.pct_change()

def corr_block(r, start, end, tag):
    sub = r.loc[start:end].dropna(how='all')
    print(f"\n=== {tag} ({start}~{end}) ===")
    # 只保留该期有足够数据的列
    valid = [c for c in sub.columns if sub[c].notna().sum() > 100]
    print(sub[valid].corr().round(2).to_string())

# 决策前: 2014-2018 (2019年初你能看到的历史)
corr_block(ret, "2014-01-01", "2018-12-31", "决策前 2014-2018")
# 观察期: 2019-2026 (用户看到的结果期)
corr_block(ret, "2019-01-18", "2026-07-08", "观察期 2019-2026")

# 关键对: 结构是否稳定?
print("\n=== 关键低相关对: 决策前 vs 观察期 ===")
pairs = [("沪深300","纳指"),("沪深300","黄金"),("沪深300","标普500"),
         ("创业板","黄金"),("纳指","黄金"),("沪深300","十年国债")]
for a,b in pairs:
    if a in ret.columns and b in ret.columns:
        c1 = ret.loc["2014-01-01":"2018-12-31",[a,b]].dropna()
        c2 = ret.loc["2019-01-18":"2026-07-08",[a,b]].dropna()
        v1 = c1[a].corr(c1[b]) if len(c1)>100 else np.nan
        v2 = c2[a].corr(c2[b]) if len(c2)>100 else np.nan
        print(f"{a:8s}~{b:8s}  决策前 {v1:5.2f}   观察期 {v2:5.2f}")
