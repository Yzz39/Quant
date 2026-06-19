from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path("data/real_etf_daily_eastmoney.csv")
RESULT_PATH = Path("outputs/bt_03_sma_real_results.csv")
SUMMARY_PATH = Path("outputs/bt_03_sma_real_summary.md")
WINDOWS = [50, 100, 150, 200, 250]
FEE_RATE = 0.001
TRADING_DAYS = 252


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def annualized_return(equity: pd.Series) -> float:
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    years = (len(equity) - 1) / TRADING_DAYS
    return float((1 + total_return) ** (1 / years) - 1)


def annualized_sharpe(returns: pd.Series) -> float:
    returns = returns.dropna()
    std = returns.std(ddof=0)
    if std == 0 or np.isnan(std):
        return np.nan
    return float(returns.mean() / std * np.sqrt(TRADING_DAYS))


def calmar(ann_return: float, mdd: float) -> float:
    if mdd >= 0 or np.isnan(mdd):
        return np.nan
    return float(ann_return / abs(mdd))


def pct(value: float) -> str:
    return f"{value:.2%}"


def main() -> None:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], dtype={"symbol": "string"})
    df = df.sort_values(["symbol", "date"])
    rows = []
    benchmark_rows = []

    for (symbol, name), g in df.groupby(["symbol", "name"], sort=True):
        close = g["close"].astype(float).reset_index(drop=True)
        asset_return = close.pct_change().fillna(0)
        buy_hold_equity = (1 + asset_return).cumprod()
        bench_ann = annualized_return(buy_hold_equity)
        bench_mdd = max_drawdown(buy_hold_equity)
        benchmark_rows.append(
            {
                "symbol": symbol,
                "name": name,
                "strategy": "Buy & Hold",
                "total_return": float(buy_hold_equity.iloc[-1] - 1),
                "annualized_return": bench_ann,
                "max_drawdown": bench_mdd,
                "sharpe": annualized_sharpe(asset_return),
                "calmar": calmar(bench_ann, bench_mdd),
            }
        )

        for window in WINDOWS:
            sma = close.rolling(window).mean()
            raw_signal = close > sma
            position = raw_signal.shift(1).fillna(False).astype(float)
            trade = position.diff().abs().fillna(position.abs())
            strategy_return = position * asset_return - trade * FEE_RATE
            equity = (1 + strategy_return).cumprod()
            ann = annualized_return(equity)
            mdd = max_drawdown(equity)
            rows.append(
                {
                    "symbol": symbol,
                    "name": name,
                    "sma_window": window,
                    "total_return": float(equity.iloc[-1] - 1),
                    "annualized_return": ann,
                    "max_drawdown": mdd,
                    "sharpe": annualized_sharpe(strategy_return),
                    "calmar": calmar(ann, mdd),
                    "trades": int(trade.sum()),
                    "time_in_market": float(position.mean()),
                    "fee_rate": FEE_RATE,
                }
            )

    result = pd.DataFrame(rows)
    benchmark = pd.DataFrame(benchmark_rows)
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(RESULT_PATH, index=False, encoding="utf-8-sig")

    stability = result.groupby(["symbol", "name"]).agg(
        best_window=("sma_window", lambda s: int(result.loc[s.index].sort_values("total_return", ascending=False).iloc[0]["sma_window"])),
        best_total_return=("total_return", "max"),
        worst_total_return=("total_return", "min"),
        median_total_return=("total_return", "median"),
        best_max_drawdown=("max_drawdown", "max"),
        worst_max_drawdown=("max_drawdown", "min"),
        min_trades=("trades", "min"),
        max_trades=("trades", "max"),
    ).reset_index()

    lines = [
        "# bt_03 真实 ETF 数据 SMA 趋势跟踪参数区间摘要",
        "",
        "## 数据",
        "",
        f"- 数据文件：`{DATA_PATH}`",
        "- 数据源：东方财富公开 K 线接口",
        "- 复权：前复权 qfq",
        f"- 区间：{df['date'].min().date()} 至 {df['date'].max().date()}",
        f"- 成本假设：每次仓位变化扣 {FEE_RATE:.2%}",
        "- 信号：`close > SMA`，并 `shift(1)` 到下一交易日执行",
        "",
        "## 参数稳定性摘要",
        "",
        "| 标的 | 最好窗口 | 最好总收益 | 最差总收益 | 中位数总收益 | 最大回撤范围 | 交易次数范围 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in stability.itertuples(index=False):
        lines.append(
            f"| {row.symbol} {row.name} | SMA {row.best_window} | {pct(row.best_total_return)} | "
            f"{pct(row.worst_total_return)} | {pct(row.median_total_return)} | "
            f"{pct(row.worst_max_drawdown)} ~ {pct(row.best_max_drawdown)} | {row.min_trades} ~ {row.max_trades} |"
        )

    lines.extend(["", "## 买入并持有基准", "", "| 标的 | 总收益 | 年化收益 | 最大回撤 | 夏普 | 卡玛 |", "|---|---:|---:|---:|---:|---:|"])
    for row in benchmark.itertuples(index=False):
        lines.append(
            f"| {row.symbol} {row.name} | {pct(row.total_return)} | {pct(row.annualized_return)} | "
            f"{pct(row.max_drawdown)} | {row.sharpe:.3f} | {row.calmar:.3f} |"
        )

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Saved: {RESULT_PATH}")
    print(f"Saved: {SUMMARY_PATH}")
    print(stability.to_string(index=False))


if __name__ == "__main__":
    main()
