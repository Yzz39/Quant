# -*- coding: utf-8 -*-
"""拉取申万一级31个行业指数全历史日线，缓存到本地CSV。"""
import akshare as ak
import pandas as pd
import os, time

CACHE = r"D:\Quant\data\sw"
os.makedirs(CACHE, exist_ok=True)

# 1) 行业列表
info = ak.sw_index_first_info()
info = info[["行业代码", "行业名称"]].copy()
info["code6"] = info["行业代码"].str.slice(0, 6)
info.to_csv(os.path.join(CACHE, "_industry_list.csv"), index=False, encoding="utf-8-sig")
print("行业数:", len(info))

ok, fail = [], []
for _, row in info.iterrows():
    code6, name = row["code6"], row["行业名称"]
    fp = os.path.join(CACHE, code6 + ".csv")
    if os.path.exists(fp):
        ok.append(code6); continue
    for attempt in range(3):
        try:
            df = ak.index_hist_sw(symbol=code6, period="day")
            if df is None or len(df) == 0:
                raise ValueError("empty")
            df.to_csv(fp, index=False, encoding="utf-8-sig")
            ok.append(code6)
            print("OK  %s %s  rows=%d" % (code6, name, len(df)))
            break
        except Exception as e:
            print("retry %s %s attempt%d: %s" % (code6, name, attempt+1, e))
            time.sleep(2)
    else:
        fail.append(code6)
    time.sleep(0.6)

print("\n完成. ok=%d fail=%d" % (len(ok), len(fail)))
if fail:
    print("失败:", fail)
