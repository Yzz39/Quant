# -*- coding: utf-8 -*-
"""
申万一级行业：熊市/震荡市分段表现分析
问题：熊市与震荡市中，哪些行业最抗跌？是否有行业能逆势走牛？谁能穿越多轮？
数据：D:\\Quant\\data\\sw\\*.csv （申万一级行业指数日线，index_hist_sw）
"""
import os
import pandas as pd
import numpy as np

DATA = r"D:\Quant\data\sw"

# 行业代码->名称
NAMES = {
    "801010":"农林牧渔","801030":"基础化工","801040":"钢铁","801050":"有色金属",
    "801080":"电子","801880":"汽车","801110":"家用电器","801120":"食品饮料",
    "801130":"纺织服饰","801140":"轻工制造","801150":"医药生物","801160":"公用事业",
    "801170":"交通运输","801180":"房地产","801200":"商贸零售","801210":"社会服务",
    "801780":"银行","801790":"非银金融","801230":"综合","801710":"建筑材料",
    "801720":"建筑装饰","801730":"电力设备","801890":"机械设备","801740":"国防军工",
    "801750":"计算机","801760":"传媒","801770":"通信","801950":"煤炭",
    "801960":"石油石化","801970":"环保","801980":"美容护理",
}

# 圈定区间：(标签, 类型, 起, 止)
# 熊市 = 单边下跌；震荡 = 宽幅无趋势/结构市
REGIMES = [
    ("2008年金融危机大熊",   "熊市", "2007-10-16", "2008-11-04"),
    ("2011阴跌熊市",         "熊市", "2011-04-18", "2012-01-06"),
    ("2015股灾+熔断",        "熊市", "2015-06-12", "2016-01-28"),
    ("2018贸易战熊市",       "熊市", "2018-01-24", "2019-01-03"),
    ("2021-24慢熊",          "熊市", "2021-12-13", "2024-02-05"),
    ("2010宽幅震荡",         "震荡", "2010-01-01", "2010-12-31"),
    ("2013钱荒结构市",       "震荡", "2013-01-01", "2013-12-31"),
    ("2016-17蓝筹慢牛/震荡", "震荡", "2016-02-01", "2017-12-31"),
    ("2023存量博弈震荡",     "震荡", "2023-01-01", "2023-12-31"),
]

def load(code):
    fp = os.path.join(DATA, code + ".csv")
    if not os.path.exists(fp):
        return None
    df = pd.read_csv(fp)
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期").set_index("日期")
    return df["收盘"].astype(float)

# 加载全部
series = {}
for code in NAMES:
    s = load(code)
    if s is not None and len(s) > 0:
        series[code] = s

def seg_stats(s, start, end):
    """区间内收益% 和 最大回撤%"""
    seg = s[(s.index >= pd.Timestamp(start)) & (s.index <= pd.Timestamp(end))]
    if len(seg) < 5:
        return None
    ret = seg.iloc[-1] / seg.iloc[0] - 1.0
    roll_max = seg.cummax()
    dd = (seg / roll_max - 1.0).min()
    return ret * 100, dd * 100

# 逐区间分析
rank_records = []  # 用于穿越统计
for label, kind, start, end in REGIMES:
    rows = []
    for code, s in series.items():
        st = seg_stats(s, start, end)
        if st is None:
            continue
        rows.append((NAMES[code], st[0], st[1]))
    if not rows:
        continue
    dfr = pd.DataFrame(rows, columns=["行业", "区间收益%", "最大回撤%"])
    n = len(dfr)
    # 基准 = 全行业等权中位数收益
    med = dfr["区间收益%"].median()
    dfr = dfr.sort_values("区间收益%", ascending=False).reset_index(drop=True)
    dfr["超额(vs中位)%"] = (dfr["区间收益%"] - med).round(1)
    dfr["收益排名"] = range(1, n + 1)

    print("=" * 70)
    print(f"【{label}】 {kind}  {start} ~ {end}   (参与行业 {n} 个, 中位收益 {med:.1f}%)")
    print("-" * 70)
    top = dfr.head(6)
    bot = dfr.tail(4)
    print("  抗跌/领涨 TOP6:")
    for _, r in top.iterrows():
        print(f"    {r['收益排名']:>2}. {r['行业']:<6} 收益 {r['区间收益%']:>7.1f}%  回撤 {r['最大回撤%']:>7.1f}%  超额 {r['超额(vs中位)%']:>+6.1f}%")
    print("  最惨 BOTTOM4:")
    for _, r in bot.iterrows():
        print(f"    {r['收益排名']:>2}. {r['行业']:<6} 收益 {r['区间收益%']:>7.1f}%  回撤 {r['最大回撤%']:>7.1f}%")

    # 记录每个行业在该区间的分位（用前1/3判定"抗跌"）
    for _, r in dfr.iterrows():
        pct_rank = r["收益排名"] / n  # 越小越靠前
        rank_records.append((label, kind, r["行业"], r["收益排名"], n, pct_rank, r["区间收益%"]))

# 穿越统计：一个行业在多少轮里排进前1/3
print("\n" + "=" * 70)
print("【穿越多轮统计】各行业进入 '收益前1/3' 的次数（分熊市 / 震荡）")
print("=" * 70)
rr = pd.DataFrame(rank_records, columns=["区间","类型","行业","名次","总数","分位","收益%"])
rr["前1/3"] = rr["分位"] <= 1/3

def cross(kind):
    sub = rr[rr["类型"] == kind]
    total_rounds = sub["区间"].nunique()
    g = sub.groupby("行业").agg(
        参与轮数=("区间", "nunique"),
        前1_3次数=("前1/3", "sum"),
        平均分位=("分位", "mean"),
        平均收益=("收益%", "mean"),
    ).reset_index()
    g["前1/3占比"] = (g["前1_3次数"] / g["参与轮数"]).round(2)
    g = g.sort_values(["前1_3次数","平均分位"], ascending=[False, True])
    print(f"\n--- {kind}（共 {total_rounds} 轮）抗跌稳定性排行 ---")
    print(f"{'行业':<7}{'参与':>4}{'前1/3次':>7}{'占比':>7}{'均分位':>8}{'均收益%':>9}")
    for _, r in g.head(12).iterrows():
        print(f"{r['行业']:<8}{int(r['参与轮数']):>4}{int(r['前1_3次数']):>7}{r['前1/3占比']:>7.2f}{r['平均分位']:>8.2f}{r['平均收益']:>9.1f}")

cross("熊市")
cross("震荡")
print("\n完成.")
