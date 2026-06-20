from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
UNIVERSE_PATH = BASE / "data" / "etf_momentum_universe.csv"
REPORT_PATH = BASE / "outputs" / "etf_momentum_data_report.md"
CHECK_PATH = BASE / "outputs" / "etf_momentum_data_quality.csv"

EXPECTED = [
    ("512880", "证券ETF", "sector", "证券"),
    ("512800", "银行ETF", "sector", "银行"),
    ("512690", "酒ETF", "sector", "白酒/酒"),
    ("512010", "医药ETF", "sector", "医药"),
    ("512170", "医疗ETF", "sector", "医疗"),
    ("512480", "半导体ETF", "sector", "半导体"),
    ("515030", "新能源车ETF", "sector", "新能源车"),
    ("515790", "光伏ETF", "sector", "光伏"),
    ("512660", "军工ETF", "sector", "军工"),
    ("512400", "有色金属ETF", "sector", "有色金属"),
    ("515220", "煤炭ETF", "sector", "煤炭"),
    ("512980", "传媒ETF", "sector", "传媒"),
    ("515230", "软件ETF", "sector", "软件"),
    ("159995", "芯片ETF", "sector", "芯片"),
    ("159819", "人工智能ETF", "sector", "人工智能"),
    ("159928", "消费ETF", "sector", "消费"),
    ("159996", "家电ETF", "sector", "家电"),
    ("159865", "养殖ETF", "sector", "养殖"),
    ("159825", "农业ETF", "sector", "农业"),
    ("511010", "国债ETF", "defensive", "国债"),
    ("511260", "十年国债ETF", "defensive", "十年国债"),
    ("511880", "银华日利ETF", "defensive", "货币/现金"),
    ("518880", "黄金ETF", "defensive", "黄金"),
    ("510300", "沪深300ETF", "benchmark", "沪深300"),
    ("510500", "中证500ETF", "benchmark", "中证500"),
    ("159915", "创业板ETF", "benchmark", "创业板"),
]


def fmt_date(x):
    return "" if pd.isna(x) else pd.Timestamp(x).date().isoformat()


def main() -> None:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], dtype={"symbol": "string"})
    expected = pd.DataFrame(EXPECTED, columns=["symbol", "planned_name", "bucket", "theme"])
    summary = (
        df.groupby("symbol")
        .agg(
            actual_name=("name", "last"),
            rows=("date", "size"),
            start=("date", "min"),
            end=("date", "max"),
            missing_close=("close", lambda s: int(s.isna().sum())),
            avg_amount=("amount", "mean"),
            min_amount=("amount", "min"),
            adjust=("adjust", lambda s: ",".join(sorted(set(map(str, s.dropna()))))),
            source=("source", lambda s: ",".join(sorted(set(map(str, s.dropna()))))),
        )
        .reset_index()
    )
    quality = expected.merge(summary, on="symbol", how="left")
    quality["download_status"] = quality["rows"].notna().map(lambda ok: "ok" if ok else "failed")
    quality["rows"] = quality["rows"].fillna(0).astype(int)
    quality["missing_close"] = quality["missing_close"].fillna(0).astype(int)
    quality["adjust"] = quality["adjust"].fillna("qfq_planned_not_downloaded")
    quality["source"] = quality["source"].fillna("eastmoney_push2his_failed")
    quality = quality.sort_values(["bucket", "symbol"])
    quality.to_csv(CHECK_PATH, index=False, encoding="utf-8-sig")

    universe = pd.read_csv(UNIVERSE_PATH, dtype={"symbol": "string"})
    universe = universe.drop(columns=[c for c in ["download_status"] if c in universe.columns])
    universe = universe.merge(quality[["symbol", "download_status", "rows", "start", "end"]], on="symbol", how="left")
    universe.to_csv(UNIVERSE_PATH, index=False, encoding="utf-8-sig")

    ok = quality[quality["download_status"] == "ok"]
    failed = quality[quality["download_status"] != "ok"]

    lines = [
        "# ETF 动量轮动历史价格数据下载报告",
        "",
        "## 输出文件",
        "",
        f"- 价格数据：`{DATA_PATH.as_posix()}`",
        f"- 候选池元数据：`{UNIVERSE_PATH.as_posix()}`",
        f"- 数据质量摘要：`{CHECK_PATH.as_posix()}`",
        "",
        "## 复权口径确认",
        "",
        "- 数据源：东方财富 push2his K线接口，以及项目已有同源历史文件补入。",
        "- 接口参数：`klt=101` 日线，`fqt=1`。",
        "- 项目记录口径：`adjust=qfq`，即前复权。",
        "- 价格字段 `open/high/low/close` 按该前复权口径保存；成交量、成交额为接口返回值。",
        "- 用途：适合计算 ETF 历史收益率、动量排序、均线；正式回测前仍应进行异常值和流动性过滤。",
        "",
        "## 候选池说明",
        "",
        "- `sector`：行业/板块 ETF，作为动量轮动主池。",
        "- `defensive`：国债、货币、黄金等防御资产。",
        "- `benchmark`：宽基 ETF，用于对照或市场状态过滤。",
        "",
        "## 下载结果概况",
        "",
        f"- 计划 ETF 数：{len(quality)}",
        f"- 成功 ETF 数：{len(ok)}",
        f"- 失败 ETF 数：{len(failed)}",
        f"- 总行数：{len(df)}",
        f"- 数据起始：{fmt_date(df['date'].min())}",
        f"- 数据结束：{fmt_date(df['date'].max())}",
        "",
    ]

    if len(failed):
        lines.extend(["## 未获取成功的品种", ""])
        for row in failed.itertuples(index=False):
            lines.append(f"- `{row.symbol}` {row.planned_name}（{row.bucket}/{row.theme}）：东方财富接口当前断连或未返回有效数据，已在质量表中标记为 failed。")
        lines.append("")

    lines.extend([
        "## 单品种质量摘要",
        "",
        "| 状态 | 分层 | 代码 | 计划名称 | 实际名称 | 主题 | 行数 | 起始 | 结束 | 平均成交额 | 最低成交额 | 复权 | 来源 |",
        "|---|---|---|---|---|---|---:|---|---|---:|---:|---|---|",
    ])
    for row in quality.itertuples(index=False):
        lines.append(
            f"| {row.download_status} | {row.bucket} | {row.symbol} | {row.planned_name} | {'' if pd.isna(row.actual_name) else row.actual_name} | "
            f"{row.theme} | {row.rows} | {fmt_date(row.start)} | {fmt_date(row.end)} | "
            f"{0 if pd.isna(row.avg_amount) else row.avg_amount:,.0f} | {0 if pd.isna(row.min_amount) else row.min_amount:,.0f} | {row.adjust} | {row.source} |"
        )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ok={len(ok)} failed={len(failed)} rows={len(df)}")
    print(f"saved {REPORT_PATH}")
    print(f"saved {CHECK_PATH}")


if __name__ == "__main__":
    main()
