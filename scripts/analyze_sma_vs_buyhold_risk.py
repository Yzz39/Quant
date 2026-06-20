from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "real_etf_daily_eastmoney.csv"
OUT_DETAIL = BASE / "outputs" / "sma_vs_buyhold_risk_detail.csv"
OUT_REPORT = BASE / "outputs" / "sma_vs_buyhold_risk_report.md"
WINDOWS = [50, 100, 150, 200, 250]
FEE_RATE = 0.001
TRADING_DAYS = 252
TREND_THRESHOLD = 0.15


def max_drawdown(equity: pd.Series) -> float:
    if len(equity) == 0:
        return np.nan
    return float((equity / equity.cummax() - 1).min())


def annualized_return(returns: pd.Series) -> float:
    returns = returns.dropna()
    if len(returns) == 0:
        return np.nan
    total_return = float((1 + returns).prod() - 1)
    years = len(returns) / TRADING_DAYS
    if years <= 0 or 1 + total_return <= 0:
        return np.nan
    return float((1 + total_return) ** (1 / years) - 1)


def sharpe(returns: pd.Series) -> float:
    returns = returns.dropna()
    std = returns.std(ddof=0)
    if len(returns) == 0 or std == 0 or np.isnan(std):
        return np.nan
    return float(returns.mean() / std * np.sqrt(TRADING_DAYS))


def metrics(returns: pd.Series) -> tuple[float, float, float, float, float]:
    returns = returns.dropna()
    equity = (1 + returns).cumprod()
    total = float(equity.iloc[-1] - 1) if len(equity) else np.nan
    ann = annualized_return(returns)
    mdd = max_drawdown(equity)
    sr = sharpe(returns)
    calmar = float(ann / abs(mdd)) if pd.notna(ann) and pd.notna(mdd) and mdd < 0 else np.nan
    return total, ann, mdd, sr, calmar


def pct(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.2%}"


def num(value: float) -> str:
    return "" if pd.isna(value) else f"{value:.3f}"


def classify_years(data: pd.DataFrame) -> dict[str, list[int] | int]:
    yearly = (
        data.groupby("year")["asset_return"]
        .apply(lambda returns: float((1 + returns).prod() - 1))
        .reset_index(name="bh_total_return")
    )
    return {
        "all": yearly["year"].astype(int).tolist(),
        "trend": yearly.loc[yearly["bh_total_return"].abs() >= TREND_THRESHOLD, "year"].astype(int).tolist(),
        "trend_up": yearly.loc[yearly["bh_total_return"] >= TREND_THRESHOLD, "year"].astype(int).tolist(),
        "trend_down": yearly.loc[yearly["bh_total_return"] <= -TREND_THRESHOLD, "year"].astype(int).tolist(),
        "range": yearly.loc[yearly["bh_total_return"].abs() < TREND_THRESHOLD, "year"].astype(int).tolist(),
        "worst_year": int(yearly.sort_values("bh_total_return").iloc[0]["year"]),
    }


def regime_masks(data: pd.DataFrame, years: dict[str, list[int] | int]) -> list[tuple[str, pd.Series]]:
    return [
        ("全区间", pd.Series(True, index=data.index)),
        ("上涨趋势期", data["year"].isin(years["trend_up"])),
        ("下跌趋势期", data["year"].isin(years["trend_down"])),
        ("趋势期合计", data["year"].isin(years["trend"])),
        ("震荡期", data["year"].isin(years["range"])),
        ("最差年份", data["year"].eq(years["worst_year"])),
    ]


def main() -> None:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], dtype={"symbol": "string"})
    df = df.sort_values(["symbol", "date"])
    rows = []
    year_lines = []

    for (symbol, name), group in df.groupby(["symbol", "name"], sort=True):
        data = group.copy().reset_index(drop=True)
        close = data["close"].astype(float).reset_index(drop=True)
        data["asset_return"] = close.pct_change().fillna(0.0)
        data["year"] = data["date"].dt.year
        years = classify_years(data)
        year_lines.append((symbol, name, years))

        strategy_returns_by_window = {}
        for window in WINDOWS:
            sma = close.rolling(window).mean()
            raw_signal = close > sma
            position = raw_signal.shift(1).fillna(False).astype(float)
            trade = position.diff().abs().fillna(position.abs())
            strategy_returns_by_window[window] = position * data["asset_return"] - trade * FEE_RATE

        for regime, mask in regime_masks(data, years):
            part = data.loc[mask]
            if part.empty:
                continue
            bh_metrics = metrics(part["asset_return"])
            for window, strategy_return in strategy_returns_by_window.items():
                sma_metrics = metrics(strategy_return.loc[mask])
                rows.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "sma_window": window,
                        "regime": regime,
                        "start": part["date"].min().date().isoformat(),
                        "end": part["date"].max().date().isoformat(),
                        "years": ",".join(map(str, sorted(part["year"].unique()))),
                        "bh_total_return": bh_metrics[0],
                        "bh_annualized_return": bh_metrics[1],
                        "bh_max_drawdown": bh_metrics[2],
                        "bh_sharpe": bh_metrics[3],
                        "bh_calmar": bh_metrics[4],
                        "sma_total_return": sma_metrics[0],
                        "sma_annualized_return": sma_metrics[1],
                        "sma_max_drawdown": sma_metrics[2],
                        "sma_sharpe": sma_metrics[3],
                        "sma_calmar": sma_metrics[4],
                        "excess_total_return": sma_metrics[0] - bh_metrics[0],
                        "drawdown_improvement": sma_metrics[2] - bh_metrics[2],
                        "sharpe_delta": sma_metrics[3] - bh_metrics[3],
                    }
                )

    detail = pd.DataFrame(rows)
    OUT_DETAIL.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(OUT_DETAIL, index=False, encoding="utf-8-sig")

    lines = [
        "# SMA 择时 vs 买入并持有：收益、回撤、夏普与坏年份",
        "",
        "## 策略与基准",
        "",
        f"- 数据：`{DATA_PATH.as_posix()}`",
        "- 买入并持有：始终持有对应 ETF。",
        "- SMA 择时：`close > SMA(window)` 后下一交易日持仓，`close <= SMA(window)` 后下一交易日空仓。",
        f"- 参数：SMA `{WINDOWS}`；每次仓位变化扣 `{FEE_RATE:.2%}` 成本。",
        f"- 行情划分：按每个 ETF 自然年买入持有收益，`|年收益| >= {TREND_THRESHOLD:.0%}` 为趋势期，低于该阈值为震荡期；最差年份为买入持有年度收益最低的一年。",
        "",
        "## 年份划分",
        "",
    ]
    for symbol, name, years in year_lines:
        lines.extend(
            [
                f"### {symbol} {name}",
                f"- 上涨趋势：{', '.join(map(str, years['trend_up'])) if years['trend_up'] else '无'}",
                f"- 下跌趋势：{', '.join(map(str, years['trend_down'])) if years['trend_down'] else '无'}",
                f"- 震荡期：{', '.join(map(str, years['range'])) if years['range'] else '无'}",
                f"- 最差年份：{years['worst_year']}",
                "",
            ]
        )

    lines.extend(
        [
            "## 全区间：按 Calmar 选择的代表窗口",
            "",
            "| 标的 | 代表SMA | B&H总收益 | SMA总收益 | 超额 | B&H最大回撤 | SMA最大回撤 | 回撤改善 | B&H夏普 | SMA夏普 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    full = detail[detail["regime"] == "全区间"]
    for (symbol, name), group in full.groupby(["symbol", "name"], sort=True):
        pick = group.sort_values(["sma_calmar", "sma_total_return"], ascending=False).iloc[0]
        lines.append(
            f"| {symbol} {name} | {int(pick.sma_window)} | {pct(pick.bh_total_return)} | {pct(pick.sma_total_return)} | "
            f"{pct(pick.excess_total_return)} | {pct(pick.bh_max_drawdown)} | {pct(pick.sma_max_drawdown)} | "
            f"{pct(pick.drawdown_improvement)} | {num(pick.bh_sharpe)} | {num(pick.sma_sharpe)} |"
        )

    lines.extend(
        [
            "",
            "## 最差年份：按回撤改善选择的窗口",
            "",
            "| 标的 | 最差年份 | 代表SMA | B&H总收益 | SMA总收益 | 超额 | B&H最大回撤 | SMA最大回撤 | 回撤改善 | B&H夏普 | SMA夏普 |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    worst = detail[detail["regime"] == "最差年份"]
    for (symbol, name), group in worst.groupby(["symbol", "name"], sort=True):
        pick = group.sort_values(["drawdown_improvement", "sma_total_return"], ascending=False).iloc[0]
        lines.append(
            f"| {symbol} {name} | {pick.years} | {int(pick.sma_window)} | {pct(pick.bh_total_return)} | {pct(pick.sma_total_return)} | "
            f"{pct(pick.excess_total_return)} | {pct(pick.bh_max_drawdown)} | {pct(pick.sma_max_drawdown)} | "
            f"{pct(pick.drawdown_improvement)} | {num(pick.bh_sharpe)} | {num(pick.sma_sharpe)} |"
        )

    lines.extend(
        [
            "",
            "## 趋势收益代价：上涨趋势是否少赚",
            "",
            "| 标的 | 代表SMA | B&H上涨趋势收益 | SMA上涨趋势收益 | 少赚/超额 | B&H上涨趋势回撤 | SMA上涨趋势回撤 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    trend_up = detail[detail["regime"] == "上涨趋势期"]
    for (symbol, name), group in trend_up.groupby(["symbol", "name"], sort=True):
        pick = group.sort_values(["sma_calmar", "sma_total_return"], ascending=False).iloc[0]
        lines.append(
            f"| {symbol} {name} | {int(pick.sma_window)} | {pct(pick.bh_total_return)} | {pct(pick.sma_total_return)} | "
            f"{pct(pick.excess_total_return)} | {pct(pick.bh_max_drawdown)} | {pct(pick.sma_max_drawdown)} |"
        )

    lines.extend(["", "## 判断", ""])
    for (symbol, name), group in detail.groupby(["symbol", "name"], sort=True):
        full_best = group[group["regime"] == "全区间"].sort_values(["sma_calmar", "sma_total_return"], ascending=False).iloc[0]
        worst_best = group[group["regime"] == "最差年份"].sort_values(["drawdown_improvement", "sma_total_return"], ascending=False).iloc[0]
        up_group = group[group["regime"] == "上涨趋势期"]
        if not up_group.empty:
            up_best = up_group.sort_values(["sma_calmar", "sma_total_return"], ascending=False).iloc[0]
            up_sentence = f"上涨趋势中，代表窗口 SMA{int(up_best.sma_window)} 相对买入持有超额 {pct(up_best.excess_total_return)}。"
        else:
            up_sentence = "没有满足阈值的上涨趋势年份。"
        lines.append(
            f"- {symbol} {name}：全区间代表窗口 SMA{int(full_best.sma_window)} 回撤改善 {pct(full_best.drawdown_improvement)}，"
            f"总收益超额 {pct(full_best.excess_total_return)}，夏普变化 {num(full_best.sharpe_delta)}；"
            f"最差年份回撤改善 {pct(worst_best.drawdown_improvement)}。{up_sentence}"
        )

    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved: {OUT_DETAIL}")
    print(f"Saved: {OUT_REPORT}")
    print(detail.groupby(["symbol", "name", "regime"]).size().to_string())


if __name__ == "__main__":
    main()
