# -*- coding: utf-8 -*-
"""下载中债国债收益率曲线的10年期数据，输出聚宽策略所需 CSV。"""
import time
import pandas as pd
import akshare as ak

RANGES = [
    ('20191201', '20201130'),
    ('20201201', '20211130'),
    ('20211201', '20221130'),
    ('20221201', '20231130'),
    ('20231201', '20241130'),
    ('20241201', '20251130'),
    ('20251201', '20260711'),
]
OUT = r'D:\Quant\cn10y_yield.csv'

parts = []
for start, end in RANGES:
    last_error = None
    for attempt in range(3):
        try:
            raw = ak.bond_china_yield(start_date=start, end_date=end)
            part = raw.loc[
                raw['曲线名称'].eq('中债国债收益率曲线'), ['日期', '10年']
            ].copy()
            part.columns = ['date', 'yield']
            part['date'] = pd.to_datetime(part['date'])
            part['yield'] = pd.to_numeric(part['yield'], errors='coerce')
            part = part.dropna()
            if part.empty:
                raise RuntimeError('未返回中债国债收益率曲线10年期数据')
            parts.append(part)
            print('%s~%s: %d rows' % (start, end, len(part)))
            break
        except Exception as exc:
            last_error = exc
            time.sleep(2 ** attempt)
    else:
        raise RuntimeError('%s~%s 下载失败: %s' % (start, end, last_error))

out = pd.concat(parts, ignore_index=True)
out = out.sort_values('date').drop_duplicates('date', keep='last')
out['date'] = out['date'].dt.strftime('%Y-%m-%d')
out.to_csv(OUT, index=False, encoding='utf-8-sig')
print('SAVED:', OUT)
print('ROWS:', len(out))
print('RANGE:', out.iloc[0]['date'], 'to', out.iloc[-1]['date'])
print('YIELD_RANGE:', out['yield'].min(), 'to', out['yield'].max())
