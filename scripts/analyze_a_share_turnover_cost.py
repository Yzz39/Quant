from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "real_etf_daily_eastmoney.csv"
OUT_DETAIL = BASE / "outputs" / "sma_a_share_turnover_cost_detail.csv"
OUT_REPORT = BASE / "outputs" / "sma_a_share_turnover_cost_report.md"
WINDOWS = [50, 100, 150, 200, 250]
TRADING_DAYS = 252

COST_SCENARIOS = [
    {
        "scenario": "no_cost",
        "commission_rate": 0.0,
        "slippage_rate": 0.0,
        "description": "无成本，用于观察策略毛收益。",
    },
    {
        "scenario": "a_share_etf_low",
        "commission_rate": 0.0001,
        "slippage_rate": 0.0001,
        "description": "A股ETF低成本：佣金0.01% + 滑点0.01%，单边合计0.02%。",
    },
    {
        "scenario": "a_share_etf_mid",
        "commission_rate": 0.0003,
        "slippage_rate": 0.0002,
        "description": "A股ETF中性成本：佣金0.03% + 滑点0.02%，单边合计0.05%。",
    },
    {
        "scenario": "a_share_etf_high",
        "commission_rate": 0.0005,
        "slippage_rate": 0.0005,
        "description": "A股ETF高成本：佣金0.05% + 滑点0.05%，单边合计0.10%。",
    },
    {
        "scenario": "previous_0_10pct",
        "commission_rate": 0.001,
        "slippage_rate": 0.0,
        "description": "此前粗略口径：每次仓位变化0.10%。",
    },
]


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


def main() -> None:
    df = pd.read_csv(DATA_PATH, parse_dates=["date"], dtype={"symbol": "string"})
    df = df.sort_values(["symbol", "date"])
    rows = []

    for (symbol, name), group in df.groupby(["symbol", "name"], sort=True):
        data = group.copy().reset_index(drop=True)
        close = data["close"].astype(float).reset_index(drop=True)
        asset_return = close.pct_change().fillna(0.0)
        bars = len(data)
        years = bars / TRADING_DAYS
        benchmark = metrics(asset_return)

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

            for cost in COST_SCENARIOS:
                one_way_cost = cost["commission_rate"] + cost["slippage_rate"]
                cost_return = trade * one_way_cost
                net_return = gross_return - cost_return
                net_metrics = metrics(net_return)
                rows.append(
                    {
                        "symbol": symbol,
                        "name": name,
                        "sma_window": window,
                        "scenario": cost["scenario"],
                        "commission_rate": cost["commission_rate"],
                        "slippage_rate": cost["slippage_rate"],
                        "one_way_cost": one_way_cost,
                        "trade_count": trade_count,
                        "turnover_per_year": turnover_per_year,
                        "time_in_market": time_in_market,
                        "gross_total_return": gross_metrics[0],
                        "net_total_return": net_metrics[0],
                        "cost_drag_vs_gross": net_metrics[0] - gross_metrics[0],
                        "bh_total_return": benchmark[0],
                        "excess_vs_bh": net_metrics[0] - benchmark[0],
                        "net_annualized_return": net_metrics[1],
                        "net_max_drawdown": net_metrics[2],
                        "net_sharpe": net_metrics[3],
                        "net_calmar": net_metrics[4],
                        "bh_max_drawdown": benchmark[2],
                        "bh_sharpe": benchmark[3],
                    }
                )

    detail = pd.DataFrame(rows)
    OUT_DETAIL.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(OUT_DETAIL, index=False, encoding="utf-8-sig")

    lines = [
        "# A股ETF趋势跟踪换手成本检查",
        "",
        "## 成本口径",
        "",
        "- 标的为 ETF，默认不计股票印花税；若实际交易品种不是 ETF，需要另行加入卖出印花税。",
        "- 成本按每次仓位变化单边扣除：`佣金率 + 滑点率`。",
        "- 滑点是经验假设，用来模拟成交价相对信号价的不利偏移；不是交易所固定费用。",
        "",
    ]
    for cost in COST_SCENARIOS:
        lines.append(f"- `{cost['scenario']}`：{cost['description']}")

    lines.extend(
        [
            "",
            "## 中性A股ETF成本场景：佣金0.03% + 滑点0.02%",
            "",
            "| 标的 | SMA | 交易次数 | 年均换手次数 | 在场率 | 毛收益 | 净收益 | 成本拖累 | 买入持有收益 | 相对B&H | 净最大回撤 | 净夏普 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    mid = detail[detail["scenario"] == "a_share_etf_mid"]
    for row in mid.itertuples(index=False):
        lines.append(
            f"| {row.symbol} {row.name} | {int(row.sma_window)} | {int(row.trade_count)} | {num(row.turnover_per_year)} | "
            f"{pct(row.time_in_market)} | {pct(row.gross_total_return)} | {pct(row.net_total_return)} | "
            f"{pct(row.cost_drag_vs_gross)} | {pct(row.bh_total_return)} | {pct(row.excess_vs_bh)} | "
            f"{pct(row.net_max_drawdown)} | {num(row.net_sharpe)} |"
        )

    lines.extend(
        [
            "",
            "## 成本敏感性：代表参数",
            "",
            "代表参数按此前风险收益观察选择：`159915=SMA250`、`510300=SMA200`、`511010=SMA100`。",
            "",
            "| 标的 | SMA | 成本场景 | 单边成本 | 净收益 | 成本拖累 | 相对B&H | 净最大回撤 | 净夏普 |",
            "|---|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    representatives = {"159915": 250, "510300": 200, "511010": 100}
    rep = detail[detail.apply(lambda row: representatives.get(str(row["symbol"])) == row["sma_window"], axis=1)]
    scenario_order = {scenario["scenario"]: index for index, scenario in enumerate(COST_SCENARIOS)}
    rep = rep.assign(scenario_order=rep["scenario"].map(scenario_order)).sort_values(["symbol", "sma_window", "scenario_order"])
    for row in rep.itertuples(index=False):
        lines.append(
            f"| {row.symbol} {row.name} | {int(row.sma_window)} | `{row.scenario}` | {pct(row.one_way_cost)} | "
            f"{pct(row.net_total_return)} | {pct(row.cost_drag_vs_gross)} | {pct(row.excess_vs_bh)} | "
            f"{pct(row.net_max_drawdown)} | {num(row.net_sharpe)} |"
        )

    lines.extend(["", "## 判断", ""])
    for symbol, window in representatives.items():
        sub = rep[(rep["symbol"].astype(str) == symbol) & (rep["sma_window"] == window)]
        low = sub[sub["scenario"] == "a_share_etf_low"].iloc[0]
        mid_row = sub[sub["scenario"] == "a_share_etf_mid"].iloc[0]
        high = sub[sub["scenario"] == "a_share_etf_high"].iloc[0]
        lines.append(
            f"- {symbol} {mid_row['name']} SMA{window}：中性成本下净收益 {pct(mid_row.net_total_return)}，"
            f"成本拖累 {pct(mid_row.cost_drag_vs_gross)}，年均换手 {num(mid_row.turnover_per_year)} 次；"
            f"低/高成本净收益分别为 {pct(low.net_total_return)} / {pct(high.net_total_return)}。"
        )

    lines.extend(
        [
            "",
            "总体结论：中长均线的换手频率不高，A股ETF中性成本通常不会推翻权益ETF趋势跟踪的回撤控制结论；但短均线交易次数明显更多，对滑点和佣金更敏感。国债ETF收益空间较小，哪怕成本不高，也更容易被交易摩擦侵蚀。",
        ]
    )

    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved: {OUT_DETAIL}")
    print(f"Saved: {OUT_REPORT}")
    print(detail.groupby(["symbol", "name", "scenario"]).size().to_string())


if __name__ == "__main__":
    main()
