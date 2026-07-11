# -*- coding: utf-8 -*-
"""申万一级行业指数环境自检：能否拉到、历史多长、字段口径。"""
import akshare as ak
import pandas as pd

print("=== 1) 申万一级行业列表 ===")
try:
    info = ak.sw_index_first_info()
    print("shape:", info.shape)
    print(info.head(10).to_string())
    print("columns:", list(info.columns))
except Exception as e:
    print("sw_index_first_info FAILED:", repr(e))

print("\n=== 2) 单个行业历史日线（取一个测试代码）===")
# 申万一级：801010 农林牧渔 是最经典的老代码之一
for fn_name in ["index_hist_sw"]:
    try:
        fn = getattr(ak, fn_name)
        df = fn(symbol="801010", period="day")
        print(f"{fn_name}('801010','day') shape:", df.shape)
        print("columns:", list(df.columns))
        print("head:\n", df.head(3).to_string())
        print("tail:\n", df.tail(3).to_string())
    except Exception as e:
        print(f"{fn_name} FAILED:", repr(e))
