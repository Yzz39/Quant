# -*- coding: utf-8 -*-
"""抓6腿后复权(hfq)日线, 落地缓存. 逐只重试, 不并发, 绕eastmoney抽风."""
import time, os
import akshare as ak
import pandas as pd

POOL = {  # code: name  (eastmoney用纯代码)
    "512890":"红利低波","159915":"创业板","513100":"纳指",
    "518880":"黄金","159985":"豆粕","511260":"国债",
}
out = "D:/Quant/data/pool_hfq"
os.makedirs(out, exist_ok=True)

def fetch_hfq(code):
    fp=f"{out}/{code}.csv"
    if os.path.exists(fp) and os.path.getsize(fp)>1000:
        return "cached"
    for i in range(8):
        try:
            df=ak.fund_etf_hist_em(symbol=code,period="daily",
                start_date="20120101",end_date="20260708",adjust="hfq")
            if df is None or len(df)==0:
                raise ValueError("empty")
            df.to_csv(fp,index=False,encoding="utf-8-sig")
            return f"OK rows={len(df)}"
        except Exception as e:
            print(f"  {code} retry{i}: {repr(e)[:45]}"); time.sleep(4)
    return "FAILED"

for code,name in POOL.items():
    r=fetch_hfq(code)
    print(f"{code} {name}: {r}")
