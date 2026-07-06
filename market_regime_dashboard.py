# -*- coding: utf-8 -*-
"""
市况仪表盘 (Market Regime Dashboard) —— A命运版
================================================
设计逻辑：主轴定方向 + 四路否决（其余指标只有权"往下降档"，不能升档）

档位：  进攻(2) > 中性(1) > 防御(0)

主轴（决定基准档）：
    沪深300 vs 200日年线（位置 + 斜率）
      站上年线 且 年线斜率向上  -> 基准 = 进攻(2)
      跌破年线 且 年线斜率向下  -> 基准 = 防御(0)
      其余（多空交织）          -> 基准 = 中性(1)

四路否决信号（每命中一条，档位 -1，下限锁死在防御(0)，永不升档）：
    1. 成交额历史分位 > 80%      —— 情绪过热，右侧追高风险
    2. 两融余额 20日趋势向下      —— 杠杆资金撤退，风险偏好下降
    3. 沪深300 动量为负(3月&6月)   —— 右侧趋势未确认 / 已转弱
    4. 赚钱效应弱(下跌家数占优)    —— 市场广度差【仅当日快照，不可回测】

用法：
    python market_regime_dashboard.py            # 用最新数据出当前档位
    python market_regime_dashboard.py 2024-06-30 # 指定"截至日"复盘历史档位(第4项广度会缺)

输出：
    控制台打印仪表盘表格 + 最终档位与决策提示
    D:\\Quant\\outputs\\regime_dashboard_YYYYMMDD.csv  （单行快照，可累积成历史）

依赖：akshare（已验证 1.18.64 可用）
"""

import sys
import os
import datetime as dt
import pandas as pd
import numpy as np
import akshare as ak

OUT_DIR = r"D:\Quant\outputs"

# ------------------------- 可调参数（都摆在这，第一次先按默认跑） -------------------------
MA_LONG          = 200     # 年线窗口（交易日）
MA_SLOPE_LOOKBACK = 20     # 判断年线斜率：与20个交易日前比
AMOUNT_PCT_WIN   = 250     # 成交额分位的回看窗口（约1年）
AMOUNT_HOT_PCT   = 0.80    # 成交额过热阈值（历史分位）
MARGIN_TREND_WIN = 20      # 两融趋势窗口（交易日）
MOM_SHORT_DAYS   = 60      # 3月动量（约60交易日）
MOM_LONG_DAYS    = 120     # 6月动量（约120交易日）
# ------------------------------------------------------------------------------------------

LEVEL_NAME = {2: "进攻", 1: "中性", 0: "防御"}


def _get_index_daily(symbol):
    """取指数日线（新浪源），返回 date/open/high/low/close/volume，date 升序。"""
    df = ak.stock_zh_index_daily(symbol=symbol)
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def compute_regime(as_of=None):
    """核心：计算截至 as_of 的市况档位。as_of=None 用最新。"""
    # ---------- 主轴：沪深300 ----------
    hs300 = _get_index_daily("sh000300")
    if as_of is not None:
        hs300 = hs300[hs300["date"] <= pd.to_datetime(as_of)]
    if len(hs300) < MA_LONG + MA_SLOPE_LOOKBACK + 5:
        raise RuntimeError("沪深300历史长度不足以计算年线")

    hs300 = hs300.reset_index(drop=True)
    close = hs300["close"]
    ma_long = close.rolling(MA_LONG).mean()

    last_close   = close.iloc[-1]
    last_ma      = ma_long.iloc[-1]
    ma_prev      = ma_long.iloc[-1 - MA_SLOPE_LOOKBACK]
    ma_slope_up  = last_ma > ma_prev
    above_ma     = last_close > last_ma
    as_of_date   = hs300["date"].iloc[-1].date()

    # 主轴基准档
    if above_ma and ma_slope_up:
        base = 2  # 进攻
    elif (not above_ma) and (not ma_slope_up):
        base = 0  # 防御
    else:
        base = 1  # 中性

    # ---------- 动量（沪深300 3月 & 6月）----------
    mom_3m = last_close / close.iloc[-1 - MOM_SHORT_DAYS] - 1
    mom_6m = last_close / close.iloc[-1 - MOM_LONG_DAYS] - 1
    mom_negative = (mom_3m < 0) and (mom_6m < 0)

    # ---------- 成交额历史分位（上证综指成交量代理全市场情绪）----------
    szzs = _get_index_daily("sh000001")
    if as_of is not None:
        szzs = szzs[szzs["date"] <= pd.to_datetime(as_of)]
    szzs = szzs.reset_index(drop=True)
    vol = szzs["volume"].astype(float)
    win = vol.tail(AMOUNT_PCT_WIN)
    last_vol = vol.iloc[-1]
    amount_pct = (win < last_vol).mean()  # 当前成交量在近1年中的分位
    amount_hot = amount_pct > AMOUNT_HOT_PCT

    # ---------- 两融余额 20日趋势 ----------
    # 注意：ak.stock_margin_sse() 不带参数会返回一段陈旧历史(曾见截止2023-09)，
    # 必须带明确 start/end 日期区间拉取，并做"陈旧性护栏"：
    # 数据末日距 as_of 超过 STALE_DAYS 天，判为不可信 -> 标 N/A，绝不拿僵尸数据充当前。
    STALE_DAYS = 15
    margin_trend_down = False
    margin_chg = np.nan
    margin_note = "N/A"
    try:
        end_dt = pd.to_datetime(as_of) if as_of is not None else pd.Timestamp.today()
        start_dt = end_dt - pd.Timedelta(days=120)  # 拉约4个月，够算20日趋势
        m = ak.stock_margin_sse(start_date=start_dt.strftime("%Y%m%d"),
                                end_date=end_dt.strftime("%Y%m%d"))
        m = m.rename(columns={"信用交易日期": "date", "融资余额": "rzye"})
        m["date"] = pd.to_datetime(m["date"].astype(str))
        m = m.sort_values("date")
        m = m[m["date"] <= end_dt]  # point-in-time，防未来函数
        rz = pd.to_numeric(m["rzye"], errors="coerce")
        m = m.assign(rzye=rz).dropna(subset=["rzye"])
        if len(m) > MARGIN_TREND_WIN:
            last_date = m["date"].iloc[-1]
            stale = (end_dt - last_date).days > STALE_DAYS
            if stale:
                margin_note = f"数据陈旧(末日{last_date.date()})→跳过"
            else:
                margin_chg = m["rzye"].iloc[-1] / m["rzye"].iloc[-1 - MARGIN_TREND_WIN] - 1
                margin_trend_down = margin_chg < 0
                margin_note = f"{margin_chg:+.1%}"
        else:
            margin_note = "数据不足→跳过"
    except Exception as e:
        margin_note = "获取失败→跳过"
        print("  [warn] 两融数据获取失败，本项否决跳过：", repr(e)[:80])

    # ---------- 赚钱效应（仅当日快照，历史复盘时不可用）----------
    breadth_weak = False
    breadth_note = "N/A(历史复盘不可用)"
    breadth_live = (as_of is None)
    if breadth_live:
        try:
            act = ak.stock_market_activity_legu()
            act = act.set_index("item")["value"]
            up = float(act.get("上涨", np.nan))
            down = float(act.get("下跌", np.nan))
            if np.isfinite(up) and np.isfinite(down) and (up + down) > 0:
                up_ratio = up / (up + down)
                breadth_weak = up_ratio < 0.40   # 上涨家数占比不足四成 = 广度差
                breadth_note = f"上涨占比 {up_ratio:.0%} (涨{int(up)}/跌{int(down)})"
        except Exception as e:
            breadth_note = "获取失败"
            print("  [warn] 赚钱效应获取失败：", repr(e)[:80])

    # ---------- 汇总：主轴档 - 否决数（锁死在0）----------
    vetoes = []
    if amount_hot:        vetoes.append(f"成交额过热(分位{amount_pct:.0%}>{AMOUNT_HOT_PCT:.0%})")
    if margin_trend_down: vetoes.append(f"两融{MARGIN_TREND_WIN}日趋势向下({margin_chg:+.1%})")
    if mom_negative:      vetoes.append(f"动量转负(3月{mom_3m:+.1%}/6月{mom_6m:+.1%})")
    if breadth_weak:      vetoes.append(f"广度差({breadth_note})")

    final = max(0, base - len(vetoes))

    return {
        "as_of_date": as_of_date,
        "close": last_close, "ma_long": last_ma,
        "above_ma": above_ma, "ma_slope_up": ma_slope_up,
        "base_level": base,
        "mom_3m": mom_3m, "mom_6m": mom_6m, "mom_negative": mom_negative,
        "amount_pct": amount_pct, "amount_hot": amount_hot,
        "margin_chg": margin_chg, "margin_trend_down": margin_trend_down, "margin_note": margin_note,
        "breadth_note": breadth_note, "breadth_weak": breadth_weak, "breadth_live": breadth_live,
        "vetoes": vetoes, "final_level": final,
    }


def render(r):
    """打印仪表盘 + 写CSV。"""
    print("\n" + "=" * 60)
    print(f"  市况仪表盘  ·  截至 {r['as_of_date']}")
    print("=" * 60)

    print("\n【主轴】沪深300 vs 200日年线")
    print(f"    收盘 {r['close']:.1f}  年线 {r['ma_long']:.1f}"
          f"  →  {'站上' if r['above_ma'] else '跌破'}年线 / 年线{'向上' if r['ma_slope_up'] else '走平或向下'}")
    print(f"    主轴基准档 = 【{LEVEL_NAME[r['base_level']]}】")

    print("\n【四路否决信号】(命中即降一档，下限锁死防御)")
    def mark(hit): return "⚠ 命中" if hit else "· 未触发"
    print(f"    1. 成交额分位  {r['amount_pct']:.0%}"
          f"        {mark(r['amount_hot'])}")
    mc = r.get('margin_note', 'N/A')
    print(f"    2. 两融20日趋势 {mc}"
          f"       {mark(r['margin_trend_down'])}")
    print(f"    3. 动量 3月{r['mom_3m']:+.1%} / 6月{r['mom_6m']:+.1%}"
          f"   {mark(r['mom_negative'])}")
    live_tag = "" if r['breadth_live'] else " [历史复盘不可用]"
    print(f"    4. 赚钱效应   {r['breadth_note']}{live_tag}"
          f"   {mark(r['breadth_weak'])}")

    print("\n" + "-" * 60)
    if r['vetoes']:
        print("  触发否决：")
        for v in r['vetoes']:
            print(f"    ⚠  {v}")
    else:
        print("  无否决信号触发")
    print("-" * 60)
    print(f"\n  >>> 最终档位：【{LEVEL_NAME[r['final_level']]}】  "
          f"(主轴{LEVEL_NAME[r['base_level']]} - 否决{len(r['vetoes'])}档) <<<\n")

    hint = {
        2: "进攻档 → 可跑 ETF动量 / 趋势跟踪，正常仓位",
        1: "中性档 → 降暴露：均值回归 / 红利低波压舱，仓位打折",
        0: "防御档 → 红利低波+债，或空仓等待，控回撤优先",
    }
    print(f"  策略提示：{hint[r['final_level']]}")
    print("=" * 60 + "\n")

    # ---- 写CSV（单行，可日后累积成历史序列）----
    os.makedirs(OUT_DIR, exist_ok=True)
    row = {
        "as_of": r["as_of_date"], "close": round(r["close"], 2),
        "ma200": round(r["ma_long"], 2), "above_ma": r["above_ma"],
        "ma_slope_up": r["ma_slope_up"], "base_level": r["base_level"],
        "mom_3m": round(r["mom_3m"], 4), "mom_6m": round(r["mom_6m"], 4),
        "amount_pct": round(r["amount_pct"], 4),
        "margin_chg": round(r["margin_chg"], 4) if pd.notna(r["margin_chg"]) else None,
        "margin_note": r.get("margin_note", "N/A"),
        "breadth": r["breadth_note"],
        "vetoes": "; ".join(r["vetoes"]) if r["vetoes"] else "",
        "final_level": r["final_level"], "final_name": LEVEL_NAME[r["final_level"]],
    }
    fn = os.path.join(OUT_DIR, f"regime_dashboard_{r['as_of_date'].strftime('%Y%m%d')}.csv")
    pd.DataFrame([row]).to_csv(fn, index=False, encoding="utf-8-sig")
    print(f"  已写入：{fn}\n")


if __name__ == "__main__":
    as_of = sys.argv[1] if len(sys.argv) > 1 else None
    if as_of:
        print(f"\n[历史复盘模式] 截至日 = {as_of}（第4项赚钱效应仅当日快照，将标 N/A）")
    r = compute_regime(as_of)
    render(r)
