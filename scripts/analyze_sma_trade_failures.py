from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "real_etf_daily_eastmoney.csv"
OUT_TRADES = BASE / "outputs" / "sma_trade_failure_trades.csv"
OUT_SUMMARY_CSV = BASE / "outputs" / "sma_trade_failure_summary.csv"
OUT_REPORT = BASE / "outputs" / "sma_trade_failure_report.md"
WINDOWS = [50, 100, 150, 200, 250]
FEE_RATE = 0.001
TRADING_DAYS = 252
FALSE_BREAKOUT_MAX_DAYS = 20
LAG_STOP_GIVEBACK_THRESHOLD = 0.08


def pct(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.2%}"


def num(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.2f}"


def max_drawdown(equity: pd.Series) -> float:
    if len(equity) == 0:
        return np.nan
    return float((equity / equity.cummax() - 1).min())


def extract_trades(data: pd.DataFrame, window: int) -> list[dict[str, object]]:
    close = data["close"].astype(float).reset_index(drop=True)
    asset_return = close.pct_change().fillna(0.0)
    sma = close.rolling(window).mean()
    raw_signal = close > sma
    position = raw_signal.shift(1).fillna(False).astype(int)
    trade_change = position.diff().fillna(position)
    entries = trade_change[trade_change == 1].index.tolist()
    exits = trade_change[trade_change == -1].index.tolist()

    trades = []
    for entry_index in entries:
        later_exits = [index for index in exits if index > entry_index]
        exit_index = later_exits[0] if later_exits else len(data) - 1
        trade_returns = asset_return.iloc[entry_index : exit_index + 1].copy()
        if trade_returns.empty:
            continue
        trade_returns.iloc[0] -= FEE_RATE
        if exit_index in exits:
            trade_returns.iloc[-1] -= FEE_RATE
        equity = (1 + trade_returns).cumprod()
        total_return = float(equity.iloc[-1] - 1)
        peak_return = float(equity.max() - 1)
        giveback_from_peak = float(equity.iloc[-1] / equity.max() - 1)
        days_held = int(exit_index - entry_index + 1)
        max_dd = max_drawdown(equity)
        false_breakout = bool(days_held <= FALSE_BREAKOUT_MAX_DAYS and total_return < 0)
        lagging_stop = bool(peak_return >= LAG_STOP_GIVEBACK_THRESHOLD and giveback_from_peak <= -LAG_STOP_GIVEBACK_THRESHOLD)
        trades.append(
            {
                "entry_date": data.loc[entry_index, "date"].date().isoformat(),
                "exit_date": data.loc[exit_index, "date"].date().isoformat(),
                "entry_close": float(close.iloc[entry_index]),
                "exit_close": float(close.iloc[exit_index]),
                "days_held": days_held,
                "total_return": total_return,
                "peak_return": peak_return,
                "giveback_from_peak": giveback_from_peak,
                "max_drawdown": max_dd,
                "false_breakout": false_breakout,
                "lagging_stop": lagging_stop,
                "open_trade": exit_index not in exits,
            }
        )
    return trades


def main() -> None:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], dtype={"symbol": "string"})
    df = df.sort_values(["symbol", "date"])
    trade_rows = []

    for (symbol, name), group in df.groupby(["symbol", "name"], sort=True):
        data = group.copy().reset_index(drop=True)
        for window in WINDOWS:
            for trade_number, trade in enumerate(extract_trades(data, window), start=1):
                trade_rows.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "sma_window": window,
                        "trade_number": trade_number,
                        **trade,
                    }
                )

    trades = pd.DataFrame(trade_rows)
    OUT_TRADES.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(OUT_TRADES, index=False, encoding="utf-8-sig")

    summary = (
        trades.groupby(["symbol", "name", "sma_window"])
        .agg(
            trade_count=("trade_number", "count"),
            win_rate=("total_return", lambda returns: float((returns > 0).mean())),
            avg_trade_return=("total_return", "mean"),
            median_trade_return=("total_return", "median"),
            total_compounded_return=("total_return", lambda returns: float((1 + returns).prod() - 1)),
            avg_days_held=("days_held", "mean"),
            false_breakout_count=("false_breakout", "sum"),
            false_breakout_rate=("false_breakout", "mean"),
            false_breakout_loss=("total_return", lambda returns: float(returns[trades.loc[returns.index, "false_breakout"]].sum())),
            lagging_stop_count=("lagging_stop", "sum"),
            lagging_stop_rate=("lagging_stop", "mean"),
            avg_lagging_giveback=("giveback_from_peak", lambda returns: float(returns[trades.loc[returns.index, "lagging_stop"]].mean()) if trades.loc[returns.index, "lagging_stop"].any() else np.nan),
            worst_trade_return=("total_return", "min"),
            worst_giveback=("giveback_from_peak", "min"),
        )
        .reset_index()
    )
    summary.to_csv(OUT_SUMMARY_CSV, index=False, encoding="utf-8-sig")

    lines = [
        "# SMA 均线择时：假突破与滞后止损分析",
        "",
        "## 分析的策略",
        "",
        f"- 数据：`{DATA_PATH.as_posix()}`",
        "- 标的：数据文件中的 `159915 创业板ETF易方达`、`510300 沪深300ETF华泰柏瑞`、`511010 国债ETF国泰`。",
        f"- 参数：SMA `{WINDOWS}`。",
        "- 入场信号：当日收盘价 `close > SMA(window)`，视为趋势偏强。",
        "- 执行时点：信号 `shift(1)`，也就是下一交易日持仓，避免用当天收盘后才知道的信息在当天成交。",
        f"- 出场信号：当日收盘价 `close <= SMA(window)` 后，下一交易日空仓。每次入场/出场扣 `{FEE_RATE:.2%}` 成本。",
        "",
        "## 事件定义",
        "",
        f"- 假突破：入场后持仓不超过 `{FALSE_BREAKOUT_MAX_DAYS}` 个交易日，且该笔交易最终亏损。它衡量价格短暂站上均线后很快跌回、被来回打脸的成本。",
        f"- 滞后止损：持仓期间浮盈曾达到至少 `{LAG_STOP_GIVEBACK_THRESHOLD:.0%}`，但到出场时较持仓内峰值回吐至少 `{LAG_STOP_GIVEBACK_THRESHOLD:.0%}`。它衡量均线出场慢、把利润还回去的程度。",
        "- 注意：同一笔交易可能同时不是二者，也可能同时满足；这是交易行为诊断，不是独立新策略。",
        "",
        "## 参数汇总",
        "",
        "| 标的 | SMA | 交易数 | 胜率 | 单笔均值 | 复合收益 | 平均持仓日 | 假突破次数/比例 | 假突破损失合计 | 滞后止损次数/比例 | 平均峰值回吐 | 最差单笔 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary.itertuples(index=False):
        lines.append(
            f"| {row.symbol} {row.name} | {int(row.sma_window)} | {int(row.trade_count)} | {pct(row.win_rate)} | "
            f"{pct(row.avg_trade_return)} | {pct(row.total_compounded_return)} | {num(row.avg_days_held)} | "
            f"{int(row.false_breakout_count)}/{pct(row.false_breakout_rate)} | {pct(row.false_breakout_loss)} | "
            f"{int(row.lagging_stop_count)}/{pct(row.lagging_stop_rate)} | {pct(row.avg_lagging_giveback)} | {pct(row.worst_trade_return)} |"
        )

    lines.extend(["", "## 关键观察", ""])
    for symbol, name in summary[["symbol", "name"]].drop_duplicates().itertuples(index=False):
        sub = summary[(summary.symbol == symbol) & (summary.name == name)].copy()
        most_false = sub.sort_values(["false_breakout_rate", "false_breakout_count"], ascending=False).iloc[0]
        least_false = sub.sort_values(["false_breakout_rate", "false_breakout_count"], ascending=True).iloc[0]
        most_lag = sub.sort_values(["lagging_stop_rate", "lagging_stop_count"], ascending=False).iloc[0]
        best_compound = sub.sort_values("total_compounded_return", ascending=False).iloc[0]
        lines.extend(
            [
                f"### {symbol} {name}",
                f"- 假突破最严重：SMA{int(most_false.sma_window)}，{int(most_false.false_breakout_count)} 次，占 {pct(most_false.false_breakout_rate)}，假突破损失合计 {pct(most_false.false_breakout_loss)}。",
                f"- 假突破最少：SMA{int(least_false.sma_window)}，{int(least_false.false_breakout_count)} 次，占 {pct(least_false.false_breakout_rate)}。",
                f"- 滞后止损最明显：SMA{int(most_lag.sma_window)}，{int(most_lag.lagging_stop_count)} 次，占 {pct(most_lag.lagging_stop_rate)}，平均峰值回吐 {pct(most_lag.avg_lagging_giveback)}。",
                f"- 逐笔复合收益最高：SMA{int(best_compound.sma_window)}，复合收益 {pct(best_compound.total_compounded_return)}，交易数 {int(best_compound.trade_count)}。",
                "",
            ]
        )

    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved: {OUT_TRADES}")
    print(f"Saved: {OUT_SUMMARY_CSV}")
    print(f"Saved: {OUT_REPORT}")
    print(summary[["symbol", "name", "sma_window", "trade_count", "false_breakout_count", "lagging_stop_count"]].to_string(index=False))


if __name__ == "__main__":
    main()
