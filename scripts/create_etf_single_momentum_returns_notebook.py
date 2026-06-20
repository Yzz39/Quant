from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUT = BASE / "notesbooks" / "etf_single_momentum_returns.ipynb"


def md(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


cells = [
    md(
        """# 单个 ETF 过去 N 个月收益率\n\n本 notebook 基于 ETF 动量轮动数据，计算每个 ETF 在过去 `1/3/6/12/24/36/48/60/72` 个月的收益率。\n\n用途：\n\n- 作为 ETF 板块动量轮动的基础信号；\n- 后续可以按某个 N 月窗口做横截面排名；\n- 也可以比较不同回看窗口的稳定性。\n\n价格口径：东方财富前复权日线，项目记录为 `adjust=qfq`。\n"""
    ),
    code(
        """from pathlib import Path\n\nimport pandas as pd\nfrom pandas.tseries.offsets import DateOffset\n\nBASE = Path.cwd()\nif BASE.name.lower() in {\"notesbooks\", \"notebooks\"}:\n    BASE = BASE.parent\n\nDATA_PATH = BASE / \"data\" / \"etf_momentum_daily_eastmoney_qfq.csv\"\nOUTPUT_PATH = BASE / \"outputs\" / \"etf_single_momentum_returns.csv\"\nREPORT_PATH = BASE / \"outputs\" / \"etf_single_momentum_returns_report.md\"\n\nMONTH_WINDOWS = [1, 3, 6, 12, 24, 36, 48, 60, 72]\n\nDATA_PATH, OUTPUT_PATH, REPORT_PATH\n"""
    ),
    md(
        """## 计算口径\n\n收益率公式：\n\n```text\nreturn_n_months = current_close / lookback_close - 1\n```\n\n回看日期口径：\n\n1. 当前交易日向前推 N 个自然月；\n2. 如果目标日期不是交易日，取该 ETF 在目标日期之前最近一个可用交易日；\n3. 如果没有足够历史数据，则 `valid=False`。\n"""
    ),
    code(
        """df = pd.read_csv(DATA_PATH, parse_dates=[\"date\"], dtype={\"symbol\": \"string\"})\nrequired = {\"date\", \"symbol\", \"name\", \"bucket\", \"theme\", \"close\", \"adjust\", \"source\"}\nmissing = sorted(required - set(df.columns))\nif missing:\n    raise ValueError(f\"Missing required columns: {missing}\")\nif df.empty:\n    raise ValueError(\"Input data is empty\")\nbad_adjust = sorted(set(df[\"adjust\"].dropna()) - {\"qfq\"})\nif bad_adjust:\n    raise ValueError(f\"Unexpected adjust values: {bad_adjust}\")\n\nprint(f\"rows={len(df):,}, etfs={df['symbol'].nunique()}, start={df['date'].min().date()}, end={df['date'].max().date()}\")\ndf.head()\n"""
    ),
    code(
        """def latest_on_or_before(data: pd.DataFrame, target_date: pd.Timestamp) -> pd.Series | None:\n    eligible = data[data[\"date\"] <= target_date]\n    if eligible.empty:\n        return None\n    return eligible.iloc[-1]\n\n\ndef compute_single_symbol_returns(symbol_df: pd.DataFrame, months_list: list[int]) -> list[dict]:\n    symbol_df = symbol_df.sort_values(\"date\").reset_index(drop=True)\n    rows = []\n    for current in symbol_df.itertuples(index=False):\n        current_date = pd.Timestamp(current.date)\n        current_close = float(current.close)\n        for months in months_list:\n            target_date = current_date - DateOffset(months=months)\n            past = latest_on_or_before(symbol_df, target_date)\n            if past is None or pd.isna(past.close) or past.close <= 0:\n                past_date = pd.NaT\n                past_close = pd.NA\n                ret = pd.NA\n                actual_days = pd.NA\n                valid = False\n            else:\n                past_date = pd.Timestamp(past.date)\n                past_close = float(past.close)\n                ret = current_close / past_close - 1\n                actual_days = (current_date - past_date).days\n                valid = True\n            rows.append(\n                {\n                    \"date\": current_date,\n                    \"symbol\": current.symbol,\n                    \"name\": current.name,\n                    \"bucket\": current.bucket,\n                    \"theme\": current.theme,\n                    \"months\": months,\n                    \"lookback_target_date\": target_date,\n                    \"lookback_actual_date\": past_date,\n                    \"actual_calendar_days\": actual_days,\n                    \"current_close\": current_close,\n                    \"lookback_close\": past_close,\n                    \"return_n_months\": ret,\n                    \"valid\": valid,\n                    \"adjust\": current.adjust,\n                    \"source\": current.source,\n                }\n            )\n    return rows\n"""
    ),
    code(
        """rows = []\nfor _, symbol_df in df.sort_values([\"symbol\", \"date\"]).groupby(\"symbol\", sort=True):\n    rows.extend(compute_single_symbol_returns(symbol_df, MONTH_WINDOWS))\n\nresult = pd.DataFrame(rows)\nprint(f\"result rows={len(result):,}, etfs={result['symbol'].nunique()}, windows={MONTH_WINDOWS}\")\nresult.groupby([\"months\", \"valid\"]).size()\n"""
    ),
    code(
        """latest_date = result[\"date\"].max()\nlatest = result[(result[\"date\"] == latest_date) & (result[\"valid\"])].copy()\nlatest_rank = latest.sort_values([\"months\", \"return_n_months\"], ascending=[True, False])\n\nprint(f\"latest date: {latest_date.date()}\")\nlatest_rank[latest_rank[\"months\"].isin([1, 3, 6, 12])][\n    [\"months\", \"symbol\", \"name\", \"bucket\", \"theme\", \"lookback_actual_date\", \"return_n_months\"]\n].head(40)\n"""
    ),
    code(
        """# 查看超长窗口：24/36/48/60/72个月在最新截面的排序\nlatest_rank[latest_rank[\"months\"].isin([24, 36, 48, 60, 72])][\n    [\"months\", \"symbol\", \"name\", \"bucket\", \"theme\", \"lookback_actual_date\", \"return_n_months\"]\n].head(80)\n"""
    ),
    code(
        """def pct(value) -> str:\n    if pd.isna(value):\n        return \"\"\n    return f\"{float(value):.2%}\"\n\n\ndef make_report(result: pd.DataFrame, months_list: list[int], output_path: Path) -> str:\n    latest_date = result[\"date\"].max()\n    latest = result[(result[\"date\"] == latest_date) & result[\"valid\"]].copy()\n    latest = latest.sort_values([\"months\", \"return_n_months\"], ascending=[True, False])\n    coverage = (\n        result.groupby([\"symbol\", \"name\", \"bucket\", \"theme\", \"months\"], dropna=False)\n        .agg(rows=(\"date\", \"size\"), valid_rows=(\"valid\", \"sum\"), start=(\"date\", \"min\"), end=(\"date\", \"max\"))\n        .reset_index()\n    )\n\n    lines = [\n        \"# 单个 ETF 过去 N 个月收益率\",\n        \"\",\n        \"## 输出文件\",\n        \"\",\n        f\"- 明细结果：`{output_path.as_posix()}`\",\n        \"\",\n        \"## 计算口径\",\n        \"\",\n        \"- 输入价格：`data/etf_momentum_daily_eastmoney_qfq.csv`。\",\n        \"- 价格口径：`adjust=qfq`，前复权收盘价 `close`。\",\n        \"- 收益率公式：`return_n_months = current_close / lookback_close - 1`。\",\n        \"- 回看日期：从当前交易日向前推 N 个自然月；若目标日期不是交易日，取该 ETF 在目标日期之前最近一个可用交易日。\",\n        \"- 输出形态：长表；一行代表某 ETF 在某交易日、某 N 月窗口下的过去收益率。\",\n        \"\",\n        \"## 本次参数\",\n        \"\",\n        f\"- N 月窗口：{', '.join(map(str, months_list))}\",\n        f\"- 最新日期：{latest_date.date()}\",\n        f\"- 结果行数：{len(result)}\",\n        \"\",\n        \"## 最新日期截面的动量收益率\",\n        \"\",\n        \"| N个月 | 分层 | 代码 | 名称 | 主题 | 当前收盘 | 回看日期 | 回看收盘 | 过去N月收益率 |\",\n        \"|---:|---|---|---|---|---:|---|---:|---:|\",\n    ]\n    for row in latest.itertuples(index=False):\n        lines.append(\n            f\"| {row.months} | {row.bucket} | {row.symbol} | {row.name} | {row.theme} | \"\n            f\"{row.current_close:.4f} | {pd.Timestamp(row.lookback_actual_date).date()} | \"\n            f\"{float(row.lookback_close):.4f} | {pct(row.return_n_months)} |\"\n        )\n\n    lines.extend([\n        \"\",\n        \"## 有效样本覆盖\",\n        \"\",\n        \"| 代码 | 名称 | 分层 | 主题 | N个月 | 总行数 | 有效行数 | 起始 | 结束 |\",\n        \"|---|---|---|---|---:|---:|---:|---|---|\",\n    ])\n    for row in coverage.sort_values([\"bucket\", \"symbol\", \"months\"]).itertuples(index=False):\n        lines.append(\n            f\"| {row.symbol} | {row.name} | {row.bucket} | {row.theme} | {row.months} | \"\n            f\"{row.rows} | {int(row.valid_rows)} | {pd.Timestamp(row.start).date()} | {pd.Timestamp(row.end).date()} |\"\n        )\n    return \"\\n\".join(lines) + \"\\n\"\n"""
    ),
    code(
        """OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)\nREPORT_PATH.parent.mkdir(parents=True, exist_ok=True)\n\nresult.to_csv(OUTPUT_PATH, index=False, encoding=\"utf-8-sig\")\nREPORT_PATH.write_text(make_report(result, MONTH_WINDOWS, OUTPUT_PATH), encoding=\"utf-8\")\n\nprint(f\"Saved: {OUTPUT_PATH}\")\nprint(f\"Saved: {REPORT_PATH}\")\n"""
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Saved: {OUT}")
