from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "real_etf_daily_eastmoney.csv"
OUT_DETAIL = BASE / "outputs" / "sma_a_share_min5_turnover_cost_detail.csv"
OUT_REPORT = BASE / "outputs" / "sma_a_share_min5_turnover_cost_report.md"
WINDOWS = [50, 100, 150, 200, 250]
CAPITAL_LEVELS = [3_000, 5_000, 8_000, 10_000, 20_000, 50_000, 100_000, 200_000, 500_000, 1_000_000]
REPRESENTATIVES = {"159915": 250, "510300": 200, "511010": 100}
COMMISSION_RATE = 0.0001
MIN_COMMISSION_CNY = 5.0
SLIPPAGE_SCENARIOS = [0.0001, 0.0002, 0.0005]
TRADING_DAYS = 252


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


def cny(value: float) -> str:
    return f"{value:,.0f}"


def effective_commission_rate(capital: float, position_size: pd.Series, trade: pd.Series) -> pd.Series:
    traded_value = capital * position_size * trade
    commission_cny = np.maximum(traded_value * COMMISSION_RATE, MIN_COMMISSION_CNY)
    effective_rate = pd.Series(0.0, index=trade.index)
    active_trade = traded_value > 0
    effective_rate.loc[active_trade] = commission_cny[active_trade] / traded_value[active_trade]
    return effective_rate


def main() -> None:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], dtype={"symbol": "string"})
    df = df.sort_values(["symbol", "date"])
    rows = []

    for (symbol, name), group in df.groupby(["symbol", "name"], sort=True):
        data = group.copy().reset_index(drop=True)
        close = data["close"].astype(float).reset_index(drop=True)
        asset_return = close.pct_change().fillna(0.0)
        benchmark = metrics(asset_return)
        years = len(data) / TRADING_DAYS

        for window in WINDOWS:
            sma = close.rolling(window).mean()
            raw_signal = close > sma
            position = raw_signal.shift(1).fillna(False).astype(float)
            trade = position.diff().abs().fillna(position.abs())
            gross_return = position * asset_return
            gross_metrics = metrics(gross_return)
            trade_count = int(trade.sum())
            turnover_per_year = float(trade.sum() / years) if years > 0 else np.nan
            time_in_market = float(position.mean())

            for capital in CAPITAL_LEVELS:
                commission_rate_series = effective_commission_rate(capital, pd.Series(1.0, index=trade.index), trade)
                avg_commission_rate = float(commission_rate_series[trade > 0].mean()) if trade.sum() > 0 else 0.0
                min_commission_bind_rate = float((commission_rate_series[trade > 0] > COMMISSION_RATE).mean()) if trade.sum() > 0 else 0.0
                for slippage_rate in SLIPPAGE_SCENARIOS:
                    cost_return = trade * (commission_rate_series + slippage_rate)
                    net_return = gross_return - cost_return
                    net_metrics = metrics(net_return)
                    total_commission_cny = float((commission_rate_series * capital * trade).sum())
                    total_slippage_cny = float((slippage_rate * capital * trade).sum())
                    total_cost_cny = total_commission_cny + total_slippage_cny
                    rows.append(
                        {
                            "symbol": symbol,
                            "name": name,
                            "sma_window": window,
                            "capital_cny": capital,
                            "commission_rate": COMMISSION_RATE,
                            "min_commission_cny": MIN_COMMISSION_CNY,
                            "slippage_rate": slippage_rate,
                            "avg_effective_commission_rate": avg_commission_rate,
                            "min_commission_bind_rate": min_commission_bind_rate,
                            "trade_count": trade_count,
                            "turnover_per_year": turnover_per_year,
                            "time_in_market": time_in_market,
                            "total_commission_cny": total_commission_cny,
                            "total_slippage_cny": total_slippage_cny,
                            "total_cost_cny": total_cost_cny,
                            "gross_total_return": gross_metrics[0],
                            "net_total_return": net_metrics[0],
                            "cost_drag_vs_gross": net_metrics[0] - gross_metrics[0],
                            "bh_total_return": benchmark[0],
                            "excess_vs_bh": net_metrics[0] - benchmark[0],
                            "net_annualized_return": net_metrics[1],
                            "net_max_drawdown": net_metrics[2],
                            "net_sharpe": net_metrics[3],
                            "net_calmar": net_metrics[4],
                        }
                    )

    detail = pd.DataFrame(rows)
    OUT_DETAIL.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(OUT_DETAIL, index=False, encoding="utf-8-sig")

    lines = [
        "# A股ETF趋势跟踪换手成本检查：万1不免五",
        "",
        "## 成本口径",
        "",
        f"- 券商佣金：成交金额的 `{COMMISSION_RATE:.2%}`（万1）。",
        f"- 最低佣金：每笔 `{MIN_COMMISSION_CNY:.0f}` 元，不免五。",
        "- ETF 默认不计股票印花税；若交易股票或非 ETF 品种，需要额外加入印花税。",
        "- 滑点做三档敏感性：`0.01% / 0.02% / 0.05%` 单边。",
        "- 最低佣金临界点：`5 / 0.0001 = 50,000 元`。单笔成交低于 5 万元时，有效佣金率高于万1；本策略满仓进出，若本金≥5万元，最低佣金不再额外放大佣金率。",
        "",
        "## 代表参数：资金规模敏感性（滑点0.02%）",
        "",
        "代表参数沿用前面风险收益观察：`159915=SMA250`、`510300=SMA200`、`511010=SMA100`。",
        "",
        "| 标的 | SMA | 本金 | 交易次数 | 年均换手 | 平均有效佣金 | 最低佣金触发率 | 总佣金 | 总滑点 | 总成本 | 净收益 | 成本拖累 | 相对B&H | 净回撤 | 净夏普 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    rep = detail[
        detail.apply(lambda row: REPRESENTATIVES.get(str(row["symbol"])) == row["sma_window"], axis=1)
        & (detail["slippage_rate"] == 0.0002)
    ].sort_values(["symbol", "capital_cny"])
    for row in rep.itertuples(index=False):
        lines.append(
            f"| {row.symbol} {row.name} | {int(row.sma_window)} | {cny(row.capital_cny)} | {int(row.trade_count)} | "
            f"{num(row.turnover_per_year)} | {pct(row.avg_effective_commission_rate)} | {pct(row.min_commission_bind_rate)} | "
            f"{cny(row.total_commission_cny)} | {cny(row.total_slippage_cny)} | {cny(row.total_cost_cny)} | "
            f"{pct(row.net_total_return)} | {pct(row.cost_drag_vs_gross)} | {pct(row.excess_vs_bh)} | "
            f"{pct(row.net_max_drawdown)} | {num(row.net_sharpe)} |"
        )

    lines.extend(
        [
            "",
            "## 全参数对比：本金1万元，滑点0.02%",
            "",
            "| 标的 | SMA | 交易次数 | 年均换手 | 平均有效佣金 | 净收益 | 成本拖累 | 买入持有收益 | 相对B&H | 净回撤 | 净夏普 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    ten_k = detail[(detail["capital_cny"] == 10_000) & (detail["slippage_rate"] == 0.0002)].sort_values(["symbol", "sma_window"])
    for row in ten_k.itertuples(index=False):
        lines.append(
            f"| {row.symbol} {row.name} | {int(row.sma_window)} | {int(row.trade_count)} | {num(row.turnover_per_year)} | "
            f"{pct(row.avg_effective_commission_rate)} | {pct(row.net_total_return)} | {pct(row.cost_drag_vs_gross)} | "
            f"{pct(row.bh_total_return)} | {pct(row.excess_vs_bh)} | {pct(row.net_max_drawdown)} | {num(row.net_sharpe)} |"
        )

    lines.extend(["", "## 判断", ""])
    for symbol, window in REPRESENTATIVES.items():
        sub = rep[(rep["symbol"].astype(str) == symbol) & (rep["sma_window"] == window)]
        first = sub.iloc[0]
        last = sub.iloc[-1]
        lines.append(
            f"- {symbol} {first['name']} SMA{window}：本金{cny(first.capital_cny)}元时平均有效佣金 {pct(first.avg_effective_commission_rate)}，"
            f"净收益 {pct(first.net_total_return)}，成本拖累 {pct(first.cost_drag_vs_gross)}；"
            f"本金{cny(last.capital_cny)}元时平均有效佣金 {pct(last.avg_effective_commission_rate)}，净收益 {pct(last.net_total_return)}。"
        )

    lines.extend(
        [
            "",
            "总体结论：在满仓 ETF 趋势跟踪假设下，只要单笔成交金额达到 5 万元，万1不免五等价于单边佣金0.01%，最低5元不再额外放大成本；5万元以下小资金仍会被最低佣金显著抬高有效费率。主要成本差异来自最低佣金、滑点和交易次数。短均线换手高，成本拖累明显；中长均线年均换手约4-5次，权益ETF成本压力明显低于万5口径，但低收益标的仍需谨慎。",
        ]
    )

    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved: {OUT_DETAIL}")
    print(f"Saved: {OUT_REPORT}")
    print(detail.groupby(["symbol", "name", "capital_cny", "slippage_rate"]).size().to_string())


if __name__ == "__main__":
    main()
