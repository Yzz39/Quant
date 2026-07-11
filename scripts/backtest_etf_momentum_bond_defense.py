from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import vectorbt as vbt


BASE = Path(__file__).resolve().parents[1]
DATA_PATH = BASE / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
OUTPUT_DIR = BASE / "outputs"

LOOKBACK_DAYS = 20
REBALANCE_EVERY_DAYS = 20
TOP_N = 2
BENCHMARK_SYMBOL = "510300"
BOND_SYMBOL = "511010"
HIGH_VOL_WINDOW = 20
HIGH_VOL_THRESHOLD = 0.25
BOND_WEIGHT_HIGH_VOL = 0.20
INIT_CASH = 100_000.0
FEE_RATE = 0.0001
SLIPPAGE = 0.0001
STRESS_FEE_RATE = 0.0005
STRESS_SLIPPAGE = 0.0005
OOS_START = pd.Timestamp("2021-01-01")
PERIODS_PER_YEAR = 252

SUMMARY_PATH = OUTPUT_DIR / "etf_momentum_bond_defense_summary.csv"
DECISIONS_PATH = OUTPUT_DIR / "etf_momentum_bond_defense_decisions.csv"
DAILY_PATH = OUTPUT_DIR / "etf_momentum_bond_defense_daily.csv"
WEIGHTS_PATH = OUTPUT_DIR / "etf_momentum_bond_defense_target_weights.csv"
REPORT_PATH = OUTPUT_DIR / "etf_momentum_bond_defense_report.md"


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    raw = pd.read_csv(DATA_PATH, dtype={"symbol": "string"}, parse_dates=["date"])
    raw["symbol"] = raw["symbol"].str.strip()
    for column in ("open", "close"):
        raw[column] = pd.to_numeric(raw[column], errors="coerce")
    raw = raw.sort_values(["date", "symbol"])

    metadata = (
        raw.groupby("symbol", as_index=False)
        .agg(
            name=("name", "last"),
            bucket=("bucket", "last"),
            theme=("theme", "last"),
            first_date=("date", "min"),
            last_date=("date", "max"),
        )
        .set_index("symbol")
    )
    open_price = raw.pivot(index="date", columns="symbol", values="open").sort_index()
    close_price = raw.pivot(index="date", columns="symbol", values="close").sort_index()
    open_price = open_price.reindex(columns=close_price.columns)

    risk_symbols = metadata.index[
        metadata["bucket"].isin(["benchmark", "sector"])
    ].tolist()
    if BENCHMARK_SYMBOL not in close_price.columns:
        raise ValueError(f"Benchmark {BENCHMARK_SYMBOL} is missing from {DATA_PATH}")
    if BOND_SYMBOL not in close_price.columns:
        raise ValueError(f"Bond ETF {BOND_SYMBOL} is missing from {DATA_PATH}")
    return metadata, open_price, close_price, risk_symbols


def choose_target_weights(
    momentum: pd.Series,
    market_volatility: float,
    risk_symbols: list[str],
    tradable_next_open: pd.Series,
    *,
    use_bond_defense: bool,
) -> tuple[dict[str, float], list[str]]:
    available = momentum.reindex(risk_symbols).dropna()
    available = available[
        tradable_next_open.reindex(available.index).notna()
        & (tradable_next_open.reindex(available.index) > 0)
    ]
    selected = available.nlargest(TOP_N).index.tolist()
    if not selected:
        return {}, []

    high_volatility = (
        use_bond_defense
        and pd.notna(market_volatility)
        and market_volatility > HIGH_VOL_THRESHOLD
    )
    bond_weight = BOND_WEIGHT_HIGH_VOL if high_volatility else 0.0
    risk_weight = 1.0 - bond_weight
    weights = {symbol: risk_weight / len(selected) for symbol in selected}
    if bond_weight > 0 and pd.notna(tradable_next_open.get(BOND_SYMBOL)):
        weights[BOND_SYMBOL] = bond_weight
    return weights, selected


def build_signals(
    close_price: pd.DataFrame,
    open_price: pd.DataFrame,
    risk_symbols: list[str],
    *,
    use_bond_defense: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    momentum = close_price / close_price.shift(LOOKBACK_DAYS) - 1.0
    benchmark_return = close_price[BENCHMARK_SYMBOL].pct_change(fill_method=None)
    market_volatility = (
        benchmark_return.rolling(HIGH_VOL_WINDOW).std(ddof=1)
        * np.sqrt(PERIODS_PER_YEAR)
    )

    order_targets = pd.DataFrame(
        np.nan,
        index=close_price.index,
        columns=close_price.columns,
        dtype=float,
    )
    decisions: list[dict[str, object]] = []

    signal_positions = range(
        LOOKBACK_DAYS,
        len(close_price.index) - 1,
        REBALANCE_EVERY_DAYS,
    )
    for position in signal_positions:
        signal_date = close_price.index[position]
        trade_date = close_price.index[position + 1]
        volatility = float(market_volatility.loc[signal_date])
        weights, selected = choose_target_weights(
            momentum.loc[signal_date],
            volatility,
            risk_symbols,
            open_price.loc[trade_date],
            use_bond_defense=use_bond_defense,
        )

        order_targets.loc[trade_date] = 0.0
        for symbol, weight in weights.items():
            order_targets.loc[trade_date, symbol] = weight

        selected_momentum = [float(momentum.loc[signal_date, symbol]) for symbol in selected]
        decisions.append(
            {
                "strategy": "momentum_bond_defense" if use_bond_defense else "momentum_baseline",
                "signal_date": signal_date,
                "trade_date": trade_date,
                "selected_symbols": "|".join(selected) if selected else "CASH",
                "selected_momentum": "|".join(f"{value:.8f}" for value in selected_momentum),
                "market_volatility": volatility,
                "high_volatility": bool(
                    use_bond_defense
                    and pd.notna(volatility)
                    and volatility > HIGH_VOL_THRESHOLD
                ),
                "bond_weight": float(weights.get(BOND_SYMBOL, 0.0)),
                "target_weights": "|".join(
                    f"{symbol}:{weight:.6f}" for symbol, weight in weights.items()
                ),
            }
        )

    effective_weights = order_targets.ffill().fillna(0.0)
    return pd.DataFrame(decisions), order_targets, effective_weights


def run_portfolio(
    open_price: pd.DataFrame,
    order_targets: pd.DataFrame,
    *,
    fee_rate: float,
    slippage: float,
) -> vbt.Portfolio:
    return vbt.Portfolio.from_orders(
        close=open_price,
        size=order_targets,
        size_type="targetpercent",
        group_by=True,
        cash_sharing=True,
        call_seq="auto",
        init_cash=INIT_CASH,
        fees=fee_rate,
        slippage=slippage,
        freq="1D",
    )


def annualized_return(value: pd.Series) -> float:
    if len(value) < 2 or value.iloc[0] <= 0:
        return np.nan
    years = len(value) / PERIODS_PER_YEAR
    return float((value.iloc[-1] / value.iloc[0]) ** (1.0 / years) - 1.0)


def max_drawdown(value: pd.Series) -> float:
    return float((value / value.cummax() - 1.0).min())


def period_metrics(value: pd.Series) -> dict[str, float]:
    value = value.dropna()
    returns = value.pct_change(fill_method=None).dropna()
    cagr = annualized_return(value)
    volatility = float(returns.std(ddof=1) * np.sqrt(PERIODS_PER_YEAR))
    sharpe = (
        float(returns.mean() * PERIODS_PER_YEAR / volatility)
        if volatility > 0
        else np.nan
    )
    drawdown = max_drawdown(value)
    calmar = cagr / abs(drawdown) if drawdown < 0 else np.nan
    yearly = returns.groupby(returns.index.year).apply(lambda item: (1.0 + item).prod() - 1.0)
    return {
        "total_return": float(value.iloc[-1] / value.iloc[0] - 1.0),
        "annualized_return": cagr,
        "annualized_volatility": volatility,
        "max_drawdown": drawdown,
        "sharpe_like_no_rf": sharpe,
        "calmar": calmar,
        "worst_calendar_year": float(yearly.min()) if not yearly.empty else np.nan,
    }


def portfolio_value(pf: vbt.Portfolio) -> pd.Series:
    value = pf.value()
    if isinstance(value, pd.DataFrame):
        value = value.iloc[:, 0]
    return value.rename("portfolio_value")


def order_metrics(pf: vbt.Portfolio, value: pd.Series) -> dict[str, float]:
    orders = pf.orders.records_readable
    years = len(value) / PERIODS_PER_YEAR
    total_fees = float(orders["Fees"].sum()) if "Fees" in orders else np.nan
    if {"Size", "Price"}.issubset(orders.columns):
        traded_value = float((orders["Size"] * orders["Price"]).abs().sum())
        annual_turnover = traded_value / float(value.mean()) / years
    else:
        annual_turnover = np.nan
    return {
        "order_count": int(len(orders)),
        "total_fees": total_fees,
        "annual_turnover": annual_turnover,
    }


def metrics_rows(
    name: str,
    value: pd.Series,
    pf: vbt.Portfolio | None,
    *,
    fee_rate: float,
    slippage: float,
) -> list[dict[str, object]]:
    periods = {
        "full": value,
        "in_sample": value[value.index < OOS_START],
        "out_of_sample": value[value.index >= OOS_START],
    }
    order_info = (
        order_metrics(pf, value)
        if pf is not None
        else {"order_count": 0, "total_fees": 0.0, "annual_turnover": 0.0}
    )
    rows = []
    for period_name, period_value in periods.items():
        if len(period_value) < 2:
            continue
        rows.append(
            {
                "strategy": name,
                "period": period_name,
                "start_date": period_value.index.min().date(),
                "end_date": period_value.index.max().date(),
                "fee_rate": fee_rate,
                "slippage": slippage,
                **period_metrics(period_value),
                **order_info,
            }
        )
    return rows


def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    headers = "| " + " | ".join(frame.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(frame.columns)) + " |"
    body = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([headers, separator, *body])


def write_report(summary: pd.DataFrame, decisions: pd.DataFrame) -> None:
    display = summary.loc[
        summary["period"].isin(["full", "out_of_sample"]),
        [
            "strategy",
            "period",
            "annualized_return",
            "max_drawdown",
            "calmar",
            "annualized_volatility",
            "worst_calendar_year",
        ],
    ].copy()
    for column in (
        "annualized_return",
        "max_drawdown",
        "annualized_volatility",
        "worst_calendar_year",
    ):
        display[column] = display[column].map(lambda value: f"{value:.2%}")
    display["calmar"] = display["calmar"].map(lambda value: f"{value:.2f}")

    defense_decisions = decisions[decisions["strategy"].eq("momentum_bond_defense")]
    latest = defense_decisions.iloc[-1]
    high_vol_count = int(defense_decisions["high_volatility"].sum())
    lines = [
        "# ETF动量 + 债券防守回测",
        "",
        "## 固定规则",
        "",
        f"- 风险资产：现有数据中的宽基和行业ETF，共按点时可用数据参与排名。",
        f"- 动量与调仓：{LOOKBACK_DAYS}日动量，每{REBALANCE_EVERY_DAYS}个交易日调仓。",
        f"- 持仓：动量最高Top{TOP_N}等权，不要求动量为正。",
        f"- 防守：沪深300过去{HIGH_VOL_WINDOW}日年化波动率高于{HIGH_VOL_THRESHOLD:.0%}时，20%转入{BOND_SYMBOL}。",
        "- 信号：收盘后生成，下一交易日开盘成交。",
        f"- 基准成本：佣金{FEE_RATE:.2%}，滑点{SLIPPAGE:.2%}；另做双边5bp压力测试。",
        "",
        "## 结果",
        "",
        dataframe_to_markdown(display),
        "",
        "## 诊断",
        "",
        f"- 防守版高波动信号：{high_vol_count}/{len(defense_decisions)}次。",
        f"- 最新信号日：{pd.Timestamp(latest['signal_date']).date()}。",
        f"- 最新交易日：{pd.Timestamp(latest['trade_date']).date()}。",
        f"- 最新选择：`{latest['selected_symbols']}`。",
        f"- 最新沪深300年化波动率：{float(latest['market_volatility']):.2%}。",
        f"- 最新债券目标权重：{float(latest['bond_weight']):.0%}。",
        "",
        "## 限制",
        "",
        "- ETF池按当前数据可得性筛选，存在幸存者和事后选池偏差。",
        "- 新ETF仅在上市并积累20日数据后加入，但没有纳入已退市或当前未选中的ETF。",
        "- 前复权数据来自东方财富；结果尚未用第二数据源复核。",
        "- 25%高波动阈值来自本次预注册假设，没有做最优参数搜索。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    metadata, open_price, close_price, risk_symbols = load_data()
    del metadata

    decisions_all = []
    daily = pd.DataFrame(index=close_price.index)
    summary_rows: list[dict[str, object]] = []
    defense_effective_weights = None

    variants = [
        ("momentum_baseline", False, FEE_RATE, SLIPPAGE),
        ("momentum_bond_defense", True, FEE_RATE, SLIPPAGE),
        ("momentum_bond_defense_stress", True, STRESS_FEE_RATE, STRESS_SLIPPAGE),
    ]
    for name, use_defense, fee_rate, slippage in variants:
        decisions, order_targets, effective_weights = build_signals(
            close_price,
            open_price,
            risk_symbols,
            use_bond_defense=use_defense,
        )
        if name == "momentum_bond_defense":
            decisions_all.append(decisions)
            defense_effective_weights = effective_weights
        elif name == "momentum_baseline":
            decisions_all.append(decisions)

        pf = run_portfolio(
            open_price,
            order_targets,
            fee_rate=fee_rate,
            slippage=slippage,
        )
        value = portfolio_value(pf)
        daily[name] = value
        summary_rows.extend(
            metrics_rows(
                name,
                value,
                pf,
                fee_rate=fee_rate,
                slippage=slippage,
            )
        )

    benchmark_open = open_price[BENCHMARK_SYMBOL].dropna()
    benchmark_value = INIT_CASH * benchmark_open / benchmark_open.iloc[0]
    daily["buy_hold_510300"] = benchmark_value.reindex(daily.index)
    summary_rows.extend(
        metrics_rows(
            "buy_hold_510300",
            benchmark_value,
            None,
            fee_rate=0.0,
            slippage=0.0,
        )
    )

    summary = pd.DataFrame(summary_rows)
    decisions_output = pd.concat(decisions_all, ignore_index=True)
    daily_output = daily.reset_index(names="date")

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    decisions_output.to_csv(DECISIONS_PATH, index=False, encoding="utf-8-sig")
    daily_output.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    assert defense_effective_weights is not None
    defense_effective_weights.reset_index(names="date").to_csv(
        WEIGHTS_PATH,
        index=False,
        encoding="utf-8-sig",
    )
    write_report(summary, decisions_output)

    print(summary.to_string(index=False))
    print(f"\nReport: {REPORT_PATH}")


if __name__ == "__main__":
    main()
