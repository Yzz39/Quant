#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ETF 日线 CSV 字段检查脚本（仅使用 Python 标准库，不依赖 pandas）。

用法：
    python etf_csv_check.py your_etf_daily.csv
    python etf_csv_check.py your_etf_daily.csv --symbol 510300

功能：
    - 检查必要字段是否存在
    - 兼容常见中英文列名
    - 检查日期、排序、重复、空值
    - 检查 OHLC 价格逻辑
    - 检查成交量 / 成交额异常
    - 计算日收益率并输出极端波动日

说明：
    这是一个“数据体检”脚本，用来判断 CSV 是否适合后续分析或回测。
    它不负责判断策略本身是否有效。
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


# 列名别名字典：
# 左边是 CSV 中可能出现的原始列名，右边是脚本内部统一使用的“标准字段名”。
#
# 这里的标准字段名采用：
# 1. 全小写英文
# 2. 单词之间用下划线连接（本脚本里大多是单词本身，不需要下划线）
# 3. 尽量短但含义明确
#
# 本脚本支持的标准字段名包括：
# - date: 交易日期
# - symbol: 证券代码
# - open: 开盘价
# - high: 最高价
# - low: 最低价
# - close: 收盘价
# - volume: 成交量
# - amount: 成交额
#
# 例子：
# - "日期" -> "date"
# - "trade_date" -> "date"
# - "code" -> "symbol"
# - "收盘价" -> "close"
# - "vol" -> "volume"
COLUMN_ALIASES: Dict[str, str] = {
    "date": "date",
    "datetime": "date",
    "time": "date",
    "trade_date": "date",
    "交易日期": "date",
    "日期": "date",
    "symbol": "symbol",
    "code": "symbol",
    "ts_code": "symbol",
    "证券代码": "symbol",
    "代码": "symbol",
    "open": "open",
    "开盘": "open",
    "开盘价": "open",
    "high": "high",
    "最高": "high",
    "最高价": "high",
    "low": "low",
    "最低": "low",
    "最低价": "low",
    "close": "close",
    "收盘": "close",
    "收盘价": "close",
    "volume": "volume",
    "vol": "volume",
    "成交量": "volume",
    "amount": "amount",
    "成交额": "amount",
}

# 必要字段：没有这些列就没法继续做完整检查。
REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
# 可选字段：有的话会检查，没有也不阻止脚本运行。
OPTIONAL_COLUMNS = ["symbol", "amount"]
# 价格相关字段。
PRICE_COLUMNS = ["open", "high", "low", "close"]
# 需要尝试转成数字的字段。
NUMERIC_COLUMNS = ["open", "high", "low", "close", "volume", "amount"]
# 允许识别的日期格式。
DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
]


@dataclass
class Row:
    """
    Row 表示“CSV 中的一行数据”的结构化版本。

    含义：
    - index: 原始数据行号（从 1 开始，不含表头）
    - raw: 原始字符串字典
    - date_value: 解析后的日期对象
    - nums: 解析后的数值字段字典

    例子：
        Row(
            index=3,
            raw={"date": "2024-01-05", "close": "3.812"},
            date_value=date(2024, 1, 5),
            nums={"close": 3.812}
        )
    """

    index: int
    raw: Dict[str, str]
    date_value: Optional[date]
    nums: Dict[str, Optional[float]]


def print_section(title: str) -> None:
    """
    打印分节标题，让命令行输出更清晰。

    输入：
    - title: 章节标题文字

    输出：
    - 无返回值，只负责打印

    例子：
        print_section("1. 文件概览")

    终端效果大致会是：
        ================================================================================
        1. 文件概览
        ================================================================================
    """

    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def normalize_column_name(col: str) -> str:
    """
    把原始列名清洗成脚本内部统一使用的标准字段名。

    处理步骤：
    1. 转成字符串
    2. 去掉首尾空格
    3. 去掉 UTF-8 BOM 标记
    4. 转小写
    5. 把空格替换成下划线
    6. 再去 COLUMN_ALIASES 里查标准名

    所谓“标准字段名”，就是脚本内部统一使用的英文列名，例如：
    - date
    - symbol
    - open
    - high
    - low
    - close
    - volume
    - amount

    输入：
    - col: CSV 表头中的原始列名，比如 "日期"、"Close"、" trade_date "

    输出：
    - 返回标准字段名；如果查不到别名，就返回清洗前后的原始值

    例子：
        normalize_column_name("日期")          -> "date"
        normalize_column_name("trade_date")   -> "date"
        normalize_column_name(" Close ")      -> "close"
        normalize_column_name("成交量")        -> "volume"
        normalize_column_name("my_custom")    -> "my_custom"
    """

    raw = str(col).strip().replace("\ufeff", "")
    key = raw.lower().replace(" ", "_")
    return COLUMN_ALIASES.get(key, COLUMN_ALIASES.get(raw, key))


def try_read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]], str]:
    """
    尝试用多种常见编码读取 CSV。

    为什么要这样做：
    很多 CSV 可能来自 Excel、券商导出、网页下载，不一定都是 utf-8，
    常见还会有 gbk、gb18030 等编码。

    输入：
    - path: CSV 文件路径对象

    输出：
    - 第 1 个返回值：表头列表，例如 ["date", "open", "close"]
    - 第 2 个返回值：每一行组成的字典列表
    - 第 3 个返回值：最终成功读取时使用的编码名

    例子：
        columns, rows, enc = try_read_csv(Path("data/sample_etf_daily.csv"))

        columns 可能是：
            ["date", "symbol", "open", "high", "low", "close", "volume"]

        rows[0] 可能是：
            {
                "date": "2024-01-02",
                "symbol": "510300",
                "open": "3.812",
                ...
            }

        enc 可能是：
            "utf-8-sig"
    """

    encodings = ["utf-8-sig", "utf-8", "gbk", "gb18030"]
    last_error: Optional[Exception] = None

    for enc in encodings:
        try:
            with path.open("r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    raise ValueError("CSV 没有表头")
                rows = list(reader)
                return list(reader.fieldnames), rows, enc
        except UnicodeDecodeError as e:
            last_error = e

    raise RuntimeError(f"无法读取 CSV 编码，最后错误是：{last_error}")


def parse_date(value: str) -> Optional[date]:
    """
    尝试把字符串解析成 date 对象。

    支持的格式由 DATE_FORMATS 控制，例如：
    - 2024-01-05
    - 2024/01/05
    - 20240105
    - 2024-01-05 15:00:00

    输入：
    - value: 原始日期字符串

    输出：
    - 成功时返回 date 对象
    - 失败时返回 None

    例子：
        parse_date("2024-01-05") -> date(2024, 1, 5)
        parse_date("20240105")   -> date(2024, 1, 5)
        parse_date("")           -> None
        parse_date("abc")        -> None
    """

    text = str(value or "").strip()
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def parse_float(value: str) -> Optional[float]:
    """
    尝试把字符串解析成浮点数。

    这个函数主要用来处理价格、成交量、成交额等数值列。
    它还兼容带千分位逗号的字符串。

    输入：
    - value: 原始数值字符串，比如 "3.812"、"1,230,000"

    输出：
    - 成功时返回 float
    - 失败时返回 None

    例子：
        parse_float("3.812")       -> 3.812
        parse_float("1,230,000")   -> 1230000.0
        parse_float("")            -> None
        parse_float("abc")         -> None
    """

    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def pct(x: float) -> str:
    """
    把小数形式的收益率转成百分比字符串。

    输入：
    - x: 小数形式收益率，比如 0.0123 表示 1.23%

    输出：
    - 百分比格式字符串

    例子：
        pct(0.0123)  -> "1.230000%"
        pct(-0.056)  -> "-5.600000%"
    """

    return f"{x:.6%}"


def preview_rows(rows: Iterable[Row], cols: List[str], limit: int = 10) -> None:
    """
    把若干行数据按指定字段打印出来，常用于展示异常样例。

    输入：
    - rows: Row 对象列表或生成器
    - cols: 想展示的字段顺序
    - limit: 最多打印多少行

    说明：
    - 如果字段名是 "date_parsed"，会显示解析后的 date_value
    - 如果字段名在 NUMERIC_COLUMNS 里，会从 nums 中取值
    - 其他字段会从 raw 中取原始字符串

    例子：
        preview_rows(parsed_rows, ["date", "open", "close"], 3)

    终端效果可能像：
        行1: date=2024-01-02 | open=3.8 | close=3.82
        行2: date=2024-01-03 | open=3.82 | close=3.79
    """

    count = 0
    for r in rows:
        values = []
        for c in cols:
            if c == "date_parsed":
                values.append(str(r.date_value))
            elif c in NUMERIC_COLUMNS:
                values.append(str(r.nums.get(c)))
            else:
                values.append(str(r.raw.get(c, "")))
        print(f"行{r.index}: " + " | ".join(f"{c}={v}" for c, v in zip(cols, values)))
        count += 1
        if count >= limit:
            break


def check_etf_csv(csv_path: Path, symbol_filter: Optional[str] = None) -> int:
    """
    核心检查函数：读取 CSV、标准化列名、解析数据并输出完整检查报告。

    输入：
    - csv_path: CSV 文件路径
    - symbol_filter: 可选，只检查某一个 ETF 代码

    输出：
    - 0: 检查通过
    - 1: 数据存在问题
    - 2: 文件不存在等外部错误

    例子：
        check_etf_csv(Path("data/sample_etf_daily.csv"))
        check_etf_csv(Path("data/sample_etf_daily.csv"), "510300")

    这个函数内部主要分 9 步：
    1. 文件概览
    2. 必要字段检查
    3. 类型转换检查
    4. 日期检查
    5. 空值检查
    6. OHLC 逻辑检查
    7. 成交量 / 成交额检查
    8. 收益率检查
    9. 总结
    """

    if not csv_path.exists():
        print(f"错误：文件不存在：{csv_path}", file=sys.stderr)
        return 2

    original_columns, raw_rows, encoding = try_read_csv(csv_path)
    normalized_columns = [normalize_column_name(c) for c in original_columns]
    rename_map = dict(zip(original_columns, normalized_columns))

    normalized_rows: List[Dict[str, str]] = []
    for raw in raw_rows:
        item: Dict[str, str] = {}
        for old_col, value in raw.items():
            if old_col is None:
                continue
            item[rename_map[old_col]] = value
        normalized_rows.append(item)

    print_section("1. 文件概览")
    print(f"文件路径: {csv_path}")
    print(f"读取编码: {encoding}")
    print(f"原始行数: {len(normalized_rows):,}")
    print(f"原始字段: {original_columns}")
    print(f"标准化字段: {normalized_columns}")

    if symbol_filter and "symbol" in normalized_columns:
        before = len(normalized_rows)
        normalized_rows = [r for r in normalized_rows if str(r.get("symbol", "")).strip() == str(symbol_filter)]
        print(f"按 symbol={symbol_filter} 过滤: {before:,} -> {len(normalized_rows):,} 行")

    print_section("2. 必要字段检查")
    unique_columns = list(dict.fromkeys(normalized_columns))
    missing_required = [c for c in REQUIRED_COLUMNS if c not in unique_columns]
    present_optional = [c for c in OPTIONAL_COLUMNS if c in unique_columns]

    if missing_required:
        print(f"缺少必要字段: {missing_required}")
        print("无法继续做完整检查，请先修正字段名或补齐字段。")
        return 1

    print(f"必要字段完整: {REQUIRED_COLUMNS}")
    print(f"可选字段存在: {present_optional if present_optional else '无'}")

    parsed_rows: List[Row] = []
    for i, raw in enumerate(normalized_rows, start=1):
        nums = {col: parse_float(raw.get(col, "")) for col in NUMERIC_COLUMNS if col in unique_columns}
        parsed_rows.append(Row(index=i, raw=raw, date_value=parse_date(raw.get("date", "")), nums=nums))

    print_section("3. 类型转换检查")
    bad_date_count = sum(1 for r in parsed_rows if r.date_value is None)
    print(f"无法解析的日期数量: {bad_date_count}")
    for col in [c for c in NUMERIC_COLUMNS if c in unique_columns]:
        bad_num = sum(1 for r in parsed_rows if r.nums.get(col) is None)
        print(f"无法解析为数字的 {col} 数量: {bad_num}")

    print_section("4. 日期检查")
    valid_date_rows = [r for r in parsed_rows if r.date_value is not None]
    if not valid_date_rows:
        print("没有任何有效日期，无法继续检查时间序列。")
        return 1

    dates = [r.date_value for r in valid_date_rows if r.date_value is not None]
    print(f"日期范围: {min(dates)} ~ {max(dates)}")
    is_monotonic = all(dates[i] <= dates[i + 1] for i in range(len(dates) - 1))
    print(f"是否按日期升序排列: {'是' if is_monotonic else '否'}")

    date_counts = Counter(dates)
    duplicate_dates = {d for d, n in date_counts.items() if n > 1}
    print(f"重复日期数量: {sum(n - 1 for n in date_counts.values() if n > 1)}")
    if duplicate_dates:
        print("重复日期样例:")
        preview_rows((r for r in valid_date_rows if r.date_value in duplicate_dates), ["date", "date_parsed", "open", "close"], 10)

    print_section("5. 空值检查")
    for col in REQUIRED_COLUMNS + [c for c in OPTIONAL_COLUMNS if c in unique_columns]:
        empty_count = sum(1 for r in parsed_rows if str(r.raw.get(col, "")).strip() == "")
        print(f"{col}: {empty_count}")

    print_section("6. OHLC 价格逻辑检查")
    price_null_rows = []
    non_positive_price_rows = []
    bad_ohlc_rows = []

    for r in parsed_rows:
        prices = {c: r.nums.get(c) for c in PRICE_COLUMNS}
        if any(v is None for v in prices.values()):
            price_null_rows.append(r)
            continue
        assert all(v is not None for v in prices.values())
        o, h, l, c = prices["open"], prices["high"], prices["low"], prices["close"]
        if min(o, h, l, c) <= 0:
            non_positive_price_rows.append(r)
        if h < l or h < o or h < c or l > o or l > c:
            bad_ohlc_rows.append(r)

    print(f"价格字段存在空值或无法转数字的行数: {len(price_null_rows)}")
    print(f"价格 <= 0 的行数: {len(non_positive_price_rows)}")
    print(f"OHLC 逻辑异常行数: {len(bad_ohlc_rows)}")
    if bad_ohlc_rows:
        print("OHLC 异常样例:")
        preview_rows(bad_ohlc_rows, ["date", "open", "high", "low", "close"], 10)

    print_section("7. 成交量 / 成交额检查")
    volume_null_rows = [r for r in parsed_rows if r.nums.get("volume") is None]
    volume_non_positive_rows = [r for r in parsed_rows if r.nums.get("volume") is not None and r.nums["volume"] <= 0]
    print(f"volume 空值或无法转数字数量: {len(volume_null_rows)}")
    print(f"volume <= 0 数量: {len(volume_non_positive_rows)}")

    if "amount" in unique_columns:
        amount_null_rows = [r for r in parsed_rows if r.nums.get("amount") is None]
        amount_non_positive_rows = [r for r in parsed_rows if r.nums.get("amount") is not None and r.nums["amount"] <= 0]
        print(f"amount 空值或无法转数字数量: {len(amount_null_rows)}")
        print(f"amount <= 0 数量: {len(amount_non_positive_rows)}")

    print_section("8. 收益率检查")
    sorted_rows = sorted(
        [r for r in parsed_rows if r.date_value is not None and r.nums.get("close") is not None],
        key=lambda x: x.date_value,
    )
    ret_rows: List[Tuple[Row, float]] = []
    previous_close: Optional[float] = None
    for r in sorted_rows:
        close = r.nums["close"]
        if close is None:
            continue
        if previous_close is not None and previous_close != 0:
            ret_rows.append((r, close / previous_close - 1.0))
        previous_close = close

    if not ret_rows:
        print("可计算收益率的有效数据不足。")
    else:
        returns = [x[1] for x in ret_rows]
        max_item = max(ret_rows, key=lambda x: x[1])
        min_item = min(ret_rows, key=lambda x: x[1])
        print(f"可计算收益率天数: {len(returns):,}")
        print(f"平均日收益率: {pct(sum(returns) / len(returns))}")
        print(f"最大单日收益率: {pct(max_item[1])}")
        print(f"最小单日收益率: {pct(min_item[1])}")
        print("\n最大收益日:")
        print(f"date={max_item[0].date_value} close={max_item[0].nums['close']} ret={pct(max_item[1])}")
        print("\n最小收益日:")
        print(f"date={min_item[0].date_value} close={min_item[0].nums['close']} ret={pct(min_item[1])}")
        extreme = [(r, ret) for r, ret in ret_rows if abs(ret) > 0.12]
        print(f"绝对日收益率 > 12% 的天数: {len(extreme):,}")
        if extreme:
            print("极端收益样例:")
            for r, ret in extreme[:10]:
                print(f"行{r.index}: date={r.date_value} close={r.nums['close']} ret={pct(ret)}")

    print_section("9. 总结")
    problems: List[str] = []
    if bad_date_count > 0:
        problems.append(f"存在 {bad_date_count} 行日期无法解析")
    if duplicate_dates:
        problems.append("存在重复日期")
    if not is_monotonic:
        problems.append("日期未按升序排列，回测前必须排序")
    required_empty_total = sum(1 for r in parsed_rows for col in REQUIRED_COLUMNS if str(r.raw.get(col, "")).strip() == "")
    if required_empty_total > 0:
        problems.append("必要字段存在空值")
    if non_positive_price_rows:
        problems.append("存在非正价格")
    if bad_ohlc_rows:
        problems.append("存在 OHLC 逻辑异常")
    if volume_non_positive_rows:
        problems.append("存在 volume <= 0")

    if problems:
        print("数据存在以下问题：")
        for p in problems:
            print(f"- {p}")
        print("\n建议：先修复这些问题，再继续做收益率、均线、动量或回测分析。")
        return 1

    print("基础字段体检通过，可以继续做收益率 / 均线 / 回测学习。")
    return 0


def main() -> int:
    """
    命令行入口函数。

    它负责两件事：
    1. 解析命令行参数
    2. 调用 check_etf_csv 执行检查

    输入：
    - 无显式函数参数，参数来自命令行

    输出：
    - 返回进程退出码

    例子：
        python etf_csv_check.py data/sample_etf_daily.csv
        python etf_csv_check.py data/sample_etf_daily.csv --symbol 510300

    参数解析后的效果大致等价于：
        args.csv_path -> Path("data/sample_etf_daily.csv")
        args.symbol   -> "510300" 或 None
    """

    parser = argparse.ArgumentParser(description="ETF 日线 CSV 字段检查脚本")
    parser.add_argument("csv_path", type=Path, help="ETF 日线 CSV 文件路径")
    parser.add_argument("--symbol", type=str, default=None, help="可选：当一个 CSV 含多只 ETF 时，只检查其中一个代码")
    args = parser.parse_args()
    return check_etf_csv(args.csv_path, args.symbol)


if __name__ == "__main__":
    raise SystemExit(main())
