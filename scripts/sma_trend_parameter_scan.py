from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DATA_PATH = Path("data/sample_etf_daily.csv")
OUTPUT_PATH = Path("outputs/sma_trend_parameter_scan.csv")
WINDOWS = [50, 100, 150, 200, 250]
FEE_RATE = 0.001
TRADING_DAYS_PER_YEAR = 252


def max_drawdown(equity: pd.Series) -> float:
    drawdown = equity / equity.cummax() - 1.0
    return float(drawdown.min())


def annualized_sharpe(daily_returns: pd.Series) -> float:
    daily_returns = daily_returns.dropna()
    std = daily_returns.std(ddof=0)
    if std == 0 or np.isnan(std):
        return np.nan
    return float(daily_returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR))


def annualized_return(equity: pd.Series) -> float:
    total_return = equity.iloc[-1] / equity.iloc[0] - 1.0
    years = (len(equity) - 1) / TRADING_DAYS_PER_YEAR
    if years <= 0:
        return np.nan
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def calmar_ratio(ann_return: float, mdd: float) -> float:
    if mdd >= 0 or np.isnan(mdd):
        return np.nan
    return float(ann_return / abs(mdd))


def scan_symbol(symbol_df: pd.DataFrame) -> list[dict[str, object]]:
    symbol_df = symbol_df.sort_values("date").copy()
    close = symbol_df["close"].astype(float)
    asset_return = close.pct_change().fillna(0.0)
    rows: list[dict[str, object]] = []

    for window in WINDOWS:
        sma = close.rolling(window).mean()
        raw_signal = close > sma
        position = raw_signal.shift(1).fillna(False).astype(float)
        trade = position.diff().abs().fillna(position.abs())
        strategy_return = position * asset_return - trade * FEE_RATE
        equity = (1.0 + strategy_return).cumprod()
        total_return = float(equity.iloc[-1] - 1.0)
        ann_return = annualized_return(equity)
        mdd = max_drawdown(equity)
        trades = int(trade.sum())

        rows.append(
            {
                "symbol": str(symbol_df["symbol"].iloc[0]),
                "name": str(symbol_df["name"].iloc[0]),
                "sma_window": window,
                "start": symbol_df["date"].iloc[0].date().isoformat(),
                "end": symbol_df["date"].iloc[-1].date().isoformat(),
                "bars": len(symbol_df),
                "total_return": total_return,
                "annualized_return": ann_return,
                "max_drawdown": mdd,
                "sharpe": annualized_sharpe(strategy_return),
                "calmar": calmar_ratio(ann_return, mdd),
                "trades": trades,
                "time_in_market": float(position.mean()),
                "fee_rate": FEE_RATE,
            }
        )

    return rows


def main() -> None:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], dtype={"symbol": "string"})
    required_columns = {"date", "symbol", "name", "close"}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    results: list[dict[str, object]] = []
    for _, symbol_df in df.groupby("symbol", sort=True):
        results.extend(scan_symbol(symbol_df))

    result_df = pd.DataFrame(results).sort_values(["symbol", "sma_window"])
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    display_df = result_df.copy()
    percent_columns = [
        "total_return",
        "annualized_return",
        "max_drawdown",
        "time_in_market",
    ]
    for column in percent_columns:
        display_df[column] = (display_df[column] * 100).round(2).astype(str) + "%"
    for column in ["sharpe", "calmar"]:
        display_df[column] = display_df[column].round(3)

    print(f"Saved: {OUTPUT_PATH}")
    print(display_df.to_string(index=False))


if __name__ == "__main__":
    main()
