from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "real_etf_daily_eastmoney.csv"
OUT_DETAIL = BASE / "outputs" / "sma_regime_performance_detail.csv"
OUT_SUMMARY = BASE / "outputs" / "sma_regime_performance_summary.md"
WINDOWS = [50, 100, 150, 200, 250]
FEE_RATE = 0.001
TRADING_DAYS = 252
TREND_THRESHOLD = 0.15


def max_drawdown(equity: pd.Series) -> float:
    if len(equity) == 0:
        return np.nan
    return float((equity / equity.cummax() - 1).min())


def annualized_return_from_period_returns(returns: pd.Series) -> float:
    returns = returns.dropna()
    if len(returns) == 0:
        return np.nan
    total = float((1 + returns).prod() - 1)
    years = len(returns) / TRADING_DAYS
    if years <= 0 or 1 + total <= 0:
        return np.nan
    return float((1 + total) ** (1 / years) - 1)


def sharpe(returns: pd.Series) -> float:
    returns = returns.dropna()
    std = returns.std(ddof=0)
    if len(returns) == 0 or std == 0 or np.isnan(std):
        return np.nan
    return float(returns.mean() / std * np.sqrt(TRADING_DAYS))


def summarize_returns(returns: pd.Series) -> tuple[float, float, float, float, float]:
    returns = returns.dropna()
    equity = (1 + returns).cumprod()
    total = float(equity.iloc[-1] - 1) if len(equity) else np.nan
    ann = annualized_return_from_period_returns(returns)
    mdd = max_drawdown(equity) if len(equity) else np.nan
    sr = sharpe(returns)
    calmar = float(ann / abs(mdd)) if pd.notna(ann) and pd.notna(mdd) and mdd < 0 else np.nan
    return total, ann, mdd, sr, calmar


def pct(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.2%}"


def num(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.3f}"


def main() -> None:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], dtype={"symbol": "string"})
    df = df.sort_values(["symbol", "date"])
    rows = []
    classified = []

    for (symbol, name), group in df.groupby(["symbol", "name"], sort=True):
        data = group.copy().reset_index(drop=True)
        data["asset_return"] = data["close"].astype(float).pct_change().fillna(0)
        data["year"] = data["date"].dt.year
        yearly = (
            data.groupby("year")["asset_return"]
            .apply(lambda returns: float((1 + returns).prod() - 1))
            .reset_index(name="bh_total_return")
        )
        worst_year = int(yearly.sort_values("bh_total_return").iloc[0]["year"])
        trend_years = yearly.loc[yearly["bh_total_return"].abs() >= TREND_THRESHOLD, "year"].astype(int).tolist()
        range_years = yearly.loc[yearly["bh_total_return"].abs() < TREND_THRESHOLD, "year"].astype(int).tolist()
        trend_up_years = yearly.loc[yearly["bh_total_return"] >= TREND_THRESHOLD, "year"].astype(int).tolist()
        trend_down_years = yearly.loc[yearly["bh_total_return"] <= -TREND_THRESHOLD, "year"].astype(int).tolist()
        classified.append((symbol, name, worst_year, trend_up_years, trend_down_years, range_years, yearly))

        close = data["close"].astype(float).reset_index(drop=True)
        asset_return = data["asset_return"]
        for window in WINDOWS:
            sma = close.rolling(window).mean()
            raw_signal = close > sma
            position = raw_signal.shift(1).fillna(False).astype(float)
            trade = position.diff().abs().fillna(position.abs())
            strategy_return = position * asset_return - trade * FEE_RATE
            tmp = data[["date", "year", "asset_return"]].copy()
            tmp["strategy_return"] = strategy_return.values
            tmp["position"] = position.values
            tmp["trade"] = trade.values

            regimes = [
                ("趋势期", tmp["year"].isin(trend_years)),
                ("上涨趋势期", tmp["year"].isin(trend_up_years)),
                ("下跌趋势期", tmp["year"].isin(trend_down_years)),
                ("震荡期", tmp["year"].isin(range_years)),
                ("最差年份", tmp["year"].eq(worst_year)),
            ]
            for regime, mask in regimes:
                part = tmp.loc[mask]
                if part.empty:
                    continue
                bh = summarize_returns(part["asset_return"])
                st = summarize_returns(part["strategy_return"])
                rows.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "sma_window": window,
                        "regime": regime,
                        "start": part["date"].min().date().isoformat(),
                        "end": part["date"].max().date().isoformat(),
                        "days": len(part),
                        "years_included": ",".join(map(str, sorted(part["year"].unique()))),
                        "bh_total_return": bh[0],
                        "bh_annualized_return": bh[1],
                        "bh_max_drawdown": bh[2],
                        "bh_sharpe": bh[3],
                        "bh_calmar": bh[4],
                        "sma_total_return": st[0],
                        "sma_annualized_return": st[1],
                        "sma_max_drawdown": st[2],
                        "sma_sharpe": st[3],
                        "sma_calmar": st[4],
                        "excess_total_return": st[0] - bh[0],
                        "drawdown_improvement": st[2] - bh[2],
                        "trades": int(part["trade"].sum()),
                        "time_in_market": float(part["position"].mean()),
                    }
                )

    result = pd.DataFrame(rows)
    OUT_DETAIL.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT_DETAIL, index=False, encoding="utf-8-sig")

    lines = [
        "# SMA 均线择时：趋势期、震荡期、最差年份表现分析",
        "",
        "## 口径",
        "",
        f"- 数据：`{DATA_PATH.as_posix()}`",
        "- 策略：`close > SMA(window)` 产生信号，`shift(1)` 次日持仓，避免未来函数。",
        f"- 参数：SMA `{WINDOWS}`；每次仓位变化扣成本 `{FEE_RATE:.2%}`。",
        f"- 行情划分：按每个 ETF 的买入持有自然年收益划分，`|年收益| >= {TREND_THRESHOLD:.0%}` 为趋势期，`|年收益| < {TREND_THRESHOLD:.0%}` 为震荡期；最差年份为该 ETF 买入持有年度收益最低的一年。",
        "",
        "## 年度行情划分",
        "",
    ]
    for symbol, name, worst_year, up, down, rng, yearly in classified:
        worst_ret = float(yearly.loc[yearly["year"].eq(worst_year), "bh_total_return"].iloc[0])
        lines.extend(
            [
                f"### {symbol} {name}",
                "",
                f"- 上涨趋势年：{', '.join(map(str, up)) if up else '无'}",
                f"- 下跌趋势年：{', '.join(map(str, down)) if down else '无'}",
                f"- 震荡年：{', '.join(map(str, rng)) if rng else '无'}",
                f"- 最差年份：{worst_year}（买入持有 {pct(worst_ret)}）",
                "",
            ]
        )

    lines.extend(
        [
            "## 分行情最佳窗口（优先 Calmar，其次总收益）",
            "",
            "| 标的 | 行情 | 最佳SMA | 买入持有总收益 | SMA总收益 | 超额 | 买入持有回撤 | SMA回撤 | 回撤改善 | 夏普 | 在场率 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for (symbol, name, regime), group in result.groupby(["symbol", "name", "regime"], sort=True):
        pick = group.sort_values(["sma_calmar", "sma_total_return"], ascending=False).iloc[0]
        lines.append(
            f"| {symbol} {name} | {regime} | {int(pick.sma_window)} | {pct(pick.bh_total_return)} | "
            f"{pct(pick.sma_total_return)} | {pct(pick.excess_total_return)} | {pct(pick.bh_max_drawdown)} | "
            f"{pct(pick.sma_max_drawdown)} | {pct(pick.drawdown_improvement)} | {num(pick.sma_sharpe)} | {pct(pick.time_in_market)} |"
        )
    lines.append("")

    lines.extend(["## 关键观察", ""])
    for symbol, name in result[["symbol", "name"]].drop_duplicates().itertuples(index=False):
        sub = result[(result.symbol == symbol) & (result.name == name)]
        lines.append(f"### {symbol} {name}")
        for regime in ["上涨趋势期", "下跌趋势期", "趋势期", "震荡期", "最差年份"]:
            group = sub[sub.regime == regime]
            if group.empty:
                continue
            median_excess = group["excess_total_return"].median()
            median_dd_imp = group["drawdown_improvement"].median()
            best = group.sort_values(["sma_calmar", "sma_total_return"], ascending=False).iloc[0]
            lines.append(
                f"- {regime}：参数中位超额 {pct(median_excess)}，中位回撤改善 {pct(median_dd_imp)}；"
                f"最佳 SMA{int(best.sma_window)} 总收益 {pct(best.sma_total_return)}、最大回撤 {pct(best.sma_max_drawdown)}。"
            )
        lines.append("")

    OUT_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved: {OUT_DETAIL}")
    print(f"Saved: {OUT_SUMMARY}")
    print(result.groupby(["symbol", "name", "regime"]).size().to_string())


if __name__ == "__main__":
    main()
