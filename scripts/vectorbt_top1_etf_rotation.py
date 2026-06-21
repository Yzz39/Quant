from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt

BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
OUTPUT_DIR = BASE / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

LOOKBACK_DAYS = 42
REBALANCE_FREQUENCY = "monthly"
INIT_CASH = 100_000.0
FEE_RATE = 0.0001
SLIPPAGE = 0.0001

DAILY_VALUE_PATH = OUTPUT_DIR / "etf_top1_rotation_vectorbt_daily_value.csv"
WEIGHTS_PATH = OUTPUT_DIR / "etf_top1_rotation_vectorbt_target_weights.csv"
DECISIONS_PATH = OUTPUT_DIR / "etf_top1_rotation_vectorbt_decisions.csv"
ORDERS_PATH = OUTPUT_DIR / "etf_top1_rotation_vectorbt_orders.csv"
METRICS_PATH = OUTPUT_DIR / "etf_top1_rotation_vectorbt_metrics.csv"
REPORT_PATH = OUTPUT_DIR / "etf_top1_rotation_vectorbt_report.md"


def rebalance_dates_for_frequency(index: pd.DatetimeIndex, frequency: str) -> pd.DatetimeIndex:
    dates = pd.Series(index, index=index)
    if frequency == "weekly":
        return pd.DatetimeIndex(dates.groupby(index.to_period("W-FRI")).last().values)
    if frequency == "biweekly":
        weekly = pd.DatetimeIndex(dates.groupby(index.to_period("W-FRI")).last().values)
        return weekly[1::2]
    if frequency == "monthly":
        return pd.DatetimeIndex(dates.groupby(index.to_period("M")).last().values)
    if frequency == "quarterly":
        return pd.DatetimeIndex(dates.groupby(index.to_period("Q")).last().values)
    raise ValueError(f"Unknown frequency: {frequency}")


def max_drawdown(nav: pd.Series) -> float:
    peak = nav.cummax()
    return float((nav / peak - 1.0).min())


def annualized_return(nav: pd.Series, periods_per_year: int = 252) -> float:
    if len(nav) < 2:
        return np.nan
    total = nav.iloc[-1] / nav.iloc[0] - 1.0
    years = len(nav) / periods_per_year
    return float((1.0 + total) ** (1.0 / years) - 1.0)


def annualized_volatility(ret: pd.Series, periods_per_year: int = 252) -> float:
    return float(ret.std() * np.sqrt(periods_per_year))


def sharpe_like(ret: pd.Series, periods_per_year: int = 252) -> float:
    vol = annualized_volatility(ret, periods_per_year)
    if vol == 0 or pd.isna(vol):
        return np.nan
    return float(ret.mean() * periods_per_year / vol)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], list[str], list[str]]:
    df = pd.read_csv(DATA_PATH, dtype={"symbol": "string"}, parse_dates=["date"])
    df["symbol"] = df["symbol"].astype("string").str.strip()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.sort_values(["symbol", "date"])

    meta = (
        df.groupby("symbol")
        .agg(
            name=("name", "last"),
            bucket=("bucket", "last"),
            theme=("theme", "last"),
            first_date=("date", "min"),
            last_date=("date", "max"),
            rows=("date", "size"),
        )
        .reset_index()
    )
    close = df.pivot(index="date", columns="symbol", values="close").sort_index().sort_index(axis=1)
    sector_symbols = meta.loc[meta["bucket"].eq("sector"), "symbol"].tolist()
    defensive_symbols = meta.loc[meta["bucket"].eq("defensive"), "symbol"].tolist()
    benchmark_symbols = meta.loc[meta["bucket"].eq("benchmark"), "symbol"].tolist()
    return df, meta, close, sector_symbols, defensive_symbols, benchmark_symbols


def build_decisions_and_weights(
    close: pd.DataFrame,
    meta: pd.DataFrame,
    sector_symbols: list[str],
    defensive_symbols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    meta_by_symbol = meta.set_index("symbol")
    signal_dates = rebalance_dates_for_frequency(close.index, REBALANCE_FREQUENCY)
    momentum = close / close.shift(LOOKBACK_DAYS) - 1.0
    decisions = []

    for signal_date in signal_dates:
        row = momentum.loc[signal_date]
        sector_mom = row[sector_symbols].dropna().sort_values(ascending=False)
        defensive_mom = row[defensive_symbols].dropna().sort_values(ascending=False)

        chosen_symbol = "CASH"
        chosen_name = "空仓"
        chosen_bucket = "cash"
        chosen_theme = "现金"
        selected_momentum = 0.0
        reason = "行业和防守资产均无正动量，空仓"
        best_sector_symbol = None
        best_sector_momentum = np.nan
        best_defensive_symbol = None
        best_defensive_momentum = np.nan

        if not sector_mom.empty:
            best_sector_symbol = sector_mom.index[0]
            best_sector_momentum = float(sector_mom.iloc[0])
        if not defensive_mom.empty:
            best_defensive_symbol = defensive_mom.index[0]
            best_defensive_momentum = float(defensive_mom.iloc[0])

        if pd.notna(best_sector_momentum) and best_sector_momentum > 0:
            chosen_symbol = best_sector_symbol
            selected_momentum = best_sector_momentum
            chosen_bucket = "sector"
            reason = "Top1 行业/主题 ETF 动量为正，持有该 ETF"
        elif pd.notna(best_defensive_momentum) and best_defensive_momentum > 0:
            chosen_symbol = best_defensive_symbol
            selected_momentum = best_defensive_momentum
            chosen_bucket = "defensive"
            reason = "Top1 行业/主题 ETF 动量为负或不可用，切到正动量防守资产"

        if chosen_symbol != "CASH":
            chosen_name = meta_by_symbol.loc[chosen_symbol, "name"]
            chosen_theme = meta_by_symbol.loc[chosen_symbol, "theme"]

        decisions.append(
            {
                "signal_date": signal_date,
                "chosen_symbol": chosen_symbol,
                "chosen_name": chosen_name,
                "chosen_bucket": chosen_bucket,
                "chosen_theme": chosen_theme,
                "selected_momentum": selected_momentum,
                "best_sector_symbol": best_sector_symbol,
                "best_sector_momentum": best_sector_momentum,
                "best_defensive_symbol": best_defensive_symbol,
                "best_defensive_momentum": best_defensive_momentum,
                "reason": reason,
            }
        )

    decisions = pd.DataFrame(decisions)
    target_weights = pd.DataFrame(0.0, index=close.index, columns=close.columns)
    decision_by_date = decisions.set_index("signal_date")
    current_symbol = "CASH"
    for date in close.index:
        if current_symbol != "CASH" and current_symbol in target_weights.columns:
            target_weights.loc[date, current_symbol] = 1.0
        if date in decision_by_date.index:
            current_symbol = decision_by_date.loc[date, "chosen_symbol"]

    return decisions, target_weights


def run_vectorbt(close: pd.DataFrame, target_weights: pd.DataFrame) -> vbt.Portfolio:
    return vbt.Portfolio.from_orders(
        close=close,
        size=target_weights,
        size_type="targetpercent",
        group_by=True,
        cash_sharing=True,
        init_cash=INIT_CASH,
        fees=FEE_RATE,
        slippage=SLIPPAGE,
        freq="1D",
    )


def build_outputs(
    pf: vbt.Portfolio,
    close: pd.DataFrame,
    target_weights: pd.DataFrame,
    decisions: pd.DataFrame,
    benchmark_symbols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    value = pf.value()
    if isinstance(value, pd.DataFrame):
        value = value.iloc[:, 0]
    value = value.rename("portfolio_value")
    daily_ret = value.pct_change().fillna(0.0)
    daily = pd.DataFrame(
        {
            "date": value.index,
            "portfolio_value": value.values,
            "nav": (value / INIT_CASH).values,
            "daily_return": daily_ret.values,
        }
    )

    orders = pf.orders.records_readable.copy()
    orders.to_csv(ORDERS_PATH, index=False, encoding="utf-8-sig")

    benchmark_symbol = "510300" if "510300" in close.columns else benchmark_symbols[0]
    benchmark_ret = close[benchmark_symbol].pct_change(fill_method=None).fillna(0.0)
    benchmark_nav = (1.0 + benchmark_ret).cumprod()
    years = len(value) / 252
    order_count = len(orders)
    total_fees = float(orders["Fees"].sum()) if "Fees" in orders.columns else np.nan
    total_order_value = float((orders["Size"] * orders["Price"]).abs().sum()) if {"Size", "Price"}.issubset(orders.columns) else np.nan
    annual_traded_value_ratio = total_order_value / INIT_CASH / years if pd.notna(total_order_value) else np.nan

    metrics = pd.DataFrame(
        [
            {
                "name": "vectorbt_top1_rotation",
                "lookback_days": LOOKBACK_DAYS,
                "rebalance_frequency": REBALANCE_FREQUENCY,
                "init_cash": INIT_CASH,
                "fee_rate": FEE_RATE,
                "slippage": SLIPPAGE,
                "total_return": value.iloc[-1] / value.iloc[0] - 1.0,
                "annualized_return": annualized_return(value / INIT_CASH),
                "annualized_volatility": annualized_volatility(daily_ret),
                "max_drawdown": max_drawdown(value / INIT_CASH),
                "sharpe_like_no_rf": sharpe_like(daily_ret),
                "final_value": float(value.iloc[-1]),
                "order_count": order_count,
                "total_fees": total_fees,
                "total_order_value": total_order_value,
                "annual_traded_value_ratio": annual_traded_value_ratio,
                "cash_target_days": int(target_weights.sum(axis=1).eq(0).sum()),
            },
            {
                "name": f"buy_hold_{benchmark_symbol}",
                "lookback_days": 0,
                "rebalance_frequency": "buy_hold",
                "init_cash": INIT_CASH,
                "fee_rate": 0.0,
                "slippage": 0.0,
                "total_return": benchmark_nav.iloc[-1] / benchmark_nav.iloc[0] - 1.0,
                "annualized_return": annualized_return(benchmark_nav),
                "annualized_volatility": annualized_volatility(benchmark_ret),
                "max_drawdown": max_drawdown(benchmark_nav),
                "sharpe_like_no_rf": sharpe_like(benchmark_ret),
                "final_value": float(INIT_CASH * benchmark_nav.iloc[-1]),
                "order_count": 0,
                "total_fees": 0.0,
                "total_order_value": 0.0,
                "annual_traded_value_ratio": 0.0,
                "cash_target_days": 0,
            },
        ]
    )

    daily.to_csv(DAILY_VALUE_PATH, index=False, encoding="utf-8-sig")
    target_weights.reset_index(names="date").to_csv(WEIGHTS_PATH, index=False, encoding="utf-8-sig")
    decisions.to_csv(DECISIONS_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(METRICS_PATH, index=False, encoding="utf-8-sig")
    return daily, orders, metrics


def write_report(metrics: pd.DataFrame, decisions: pd.DataFrame, orders: pd.DataFrame) -> None:
    strategy = metrics.iloc[0]
    latest = decisions.iloc[-1]
    lines = [
        "# vectorbt Top1 ETF 轮动回测报告",
        "",
        "## 规则",
        "",
        f"- 动量窗口：`{LOOKBACK_DAYS}` 个交易日。",
        f"- 调仓频率：`{REBALANCE_FREQUENCY}`，调仓日收盘后生成信号，下一交易日目标权重生效。",
        "- 行业/主题 ETF 中选择动量最高的 Top1。",
        "- 若 Top1 行业/主题 ETF 动量为负或不可用，则切换到正动量防守资产；若防守资产也无正动量，则空仓。",
        f"- vectorbt 成本：佣金 `{FEE_RATE:.4%}`，滑点 `{SLIPPAGE:.4%}`。",
        "",
        "## 输出文件",
        "",
        f"- 每日净值：`{DAILY_VALUE_PATH.as_posix()}`",
        f"- 目标权重：`{WEIGHTS_PATH.as_posix()}`",
        f"- 调仓决策：`{DECISIONS_PATH.as_posix()}`",
        f"- 订单明细：`{ORDERS_PATH.as_posix()}`",
        f"- 指标：`{METRICS_PATH.as_posix()}`",
        "",
        "## 关键结果",
        "",
        f"- 总收益：{strategy['total_return']:.2%}",
        f"- 年化收益：{strategy['annualized_return']:.2%}",
        f"- 最大回撤：{strategy['max_drawdown']:.2%}",
        f"- 类夏普：{strategy['sharpe_like_no_rf']:.2f}",
        f"- 最终资产：{strategy['final_value']:,.2f}",
        f"- 订单数：{int(strategy['order_count'])}",
        f"- 总手续费：{strategy['total_fees']:,.2f}",
        f"- 年化成交额/初始本金：{strategy['annual_traded_value_ratio']:.2f}x",
        "",
        "## 最新信号",
        "",
        f"- 信号日：{pd.to_datetime(latest['signal_date']).date()}",
        f"- 选择：`{latest['chosen_symbol']}` {latest['chosen_name']}",
        f"- 类型：{latest['chosen_bucket']}",
        f"- 动量：{latest['selected_momentum']:.2%}",
        f"- 理由：{latest['reason']}",
        "",
        "## 订单摘要",
        "",
        f"- 订单行数：{len(orders)}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _, meta, close, sector_symbols, defensive_symbols, benchmark_symbols = load_data()
    decisions, target_weights = build_decisions_and_weights(close, meta, sector_symbols, defensive_symbols)
    pf = run_vectorbt(close, target_weights)
    daily, orders, metrics = build_outputs(pf, close, target_weights, decisions, benchmark_symbols)
    write_report(metrics, decisions, orders)

    print(f"vectorbt version: {vbt.__version__}")
    print(f"Saved daily value: {DAILY_VALUE_PATH}")
    print(f"Saved target weights: {WEIGHTS_PATH}")
    print(f"Saved decisions: {DECISIONS_PATH}")
    print(f"Saved orders: {ORDERS_PATH}")
    print(f"Saved metrics: {METRICS_PATH}")
    print(f"Saved report: {REPORT_PATH}")
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
