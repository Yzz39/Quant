from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

BASE = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = BASE / "notebooks" / "etf_momentum_1to6_month_comparison.ipynb"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(text).strip().splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": dedent(text).strip().splitlines(keepends=True)}


cells = [
    md(
        """
        # ETF 动量窗口对比：1~6 个月行业/主题 ETF 动量

        这个 notebook 用同一套数据、同一套防守/空仓规则，对比 `1, 2, 3, 4, 5, 6` 个月动量窗口。

        研究问题：

        > 6 个月动量是否太滞后？更短窗口是否更灵敏，还是只是增加噪音和换仓？

        注意：这是学习和研究样例，不构成投资建议。
        """
    ),
    md(
        """
        ## 1. 对比口径

        为了让对比公平，除动量窗口外，其它规则全部保持一致：

        - 数据：`../data/etf_momentum_daily_eastmoney_qfq.csv`
        - 行业/主题 ETF：`bucket == 'sector'`
        - 防守资产：`bucket == 'defensive'`
        - 调仓：每月末生成信号，下一个交易日生效，避免未来函数
        - 成本：每次换仓扣 `0.02%`
        - 动量定义：`当前收盘价 / N个交易日前收盘价 - 1`
        - 窗口：

        | 月数 | 交易日近似 |
        |---:|---:|
        | 1 | 21 |
        | 2 | 42 |
        | 3 | 63 |
        | 4 | 84 |
        | 5 | 105 |
        | 6 | 126 |

        规则：

        1. 每月末计算所有行业/主题 ETF 的 N 月动量；
        2. 若最佳行业 ETF 动量 `> 0`，下期持有它；
        3. 若最佳行业 ETF 动量 `<= 0`，转向防守资产；
        4. 若最佳防守资产动量 `> 0`，持有防守资产；
        5. 否则空仓。
        """
    ),
    code(
        """
        from pathlib import Path
        import numpy as np
        import pandas as pd

        BASE = Path.cwd()
        if BASE.name == "notebooks":
            BASE = BASE.parent
        DATA_PATH = BASE / "data" / "etf_momentum_daily_eastmoney_qfq.csv"
        OUTPUT_DIR = BASE / "outputs"
        OUTPUT_DIR.mkdir(exist_ok=True)

        WINDOWS = {
            "mom_1m": 21,
            "mom_2m": 42,
            "mom_3m": 63,
            "mom_4m": 84,
            "mom_5m": 105,
            "mom_6m": 126,
        }
        FEE_RATE = 0.0002
        """
    ),
    md("""## 2. 读取数据"""),
    code(
        """
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
        meta_by_symbol = meta.set_index("symbol")

        close = df.pivot(index="date", columns="symbol", values="close").sort_index()
        daily_ret = close.pct_change(fill_method=None).fillna(0.0)

        sector_symbols = meta.loc[meta["bucket"].eq("sector"), "symbol"].tolist()
        defensive_symbols = meta.loc[meta["bucket"].eq("defensive"), "symbol"].tolist()
        benchmark_symbols = meta.loc[meta["bucket"].eq("benchmark"), "symbol"].tolist()

        print(f"数据区间: {close.index.min().date()} ~ {close.index.max().date()}")
        print(f"ETF 数量: {close.shape[1]}")
        print(f"行业/主题 ETF: {len(sector_symbols)}")
        print(f"防守资产: {len(defensive_symbols)}", defensive_symbols)
        print(f"基准资产: {len(benchmark_symbols)}", benchmark_symbols)
        meta.sort_values(["bucket", "symbol"])
        """
    ),
    md("""## 3. 回测函数：单一动量窗口"""),
    code(
        """
        def month_end_trading_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
            return pd.DatetimeIndex(pd.Series(index, index=index).groupby(index.to_period("M")).last().values)


        def run_strategy_for_window(label: str, lookback_days: int) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
            rebalance_dates = month_end_trading_dates(close.index)
            momentum = close / close.shift(lookback_days) - 1.0
            decisions = []

            for signal_date in rebalance_dates:
                row = momentum.loc[signal_date]
                sector_mom = row[sector_symbols].dropna().sort_values(ascending=False)
                defensive_mom = row[defensive_symbols].dropna().sort_values(ascending=False)

                chosen_symbol = "CASH"
                chosen_bucket = "cash"
                chosen_name = "空仓"
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
                    chosen_bucket = "sector"
                    selected_momentum = best_sector_momentum
                    reason = "最佳行业/主题 ETF 动量为正，持有该 ETF"
                elif pd.notna(best_defensive_momentum) and best_defensive_momentum > 0:
                    chosen_symbol = best_defensive_symbol
                    chosen_bucket = "defensive"
                    selected_momentum = best_defensive_momentum
                    reason = "最佳行业/主题 ETF 动量为负或不可用，切换到正动量防守资产"

                if chosen_symbol != "CASH":
                    chosen_name = meta_by_symbol.loc[chosen_symbol, "name"]
                    chosen_theme = meta_by_symbol.loc[chosen_symbol, "theme"]

                decisions.append(
                    {
                        "window_label": label,
                        "lookback_days": lookback_days,
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
            positions = pd.Series("CASH", index=close.index, name="position", dtype="object")
            decision_by_date = decisions.set_index("signal_date")
            current_position = "CASH"
            for date in close.index:
                positions.loc[date] = current_position
                if date in decision_by_date.index:
                    current_position = decision_by_date.loc[date, "chosen_symbol"]

            strategy_ret = pd.Series(0.0, index=close.index, name="strategy_return")
            for symbol in close.columns:
                mask = positions.eq(symbol)
                strategy_ret.loc[mask] = daily_ret.loc[mask, symbol]

            trades = positions.ne(positions.shift(1)).fillna(False)
            trades.iloc[0] = False
            strategy_ret_after_cost = strategy_ret.copy()
            strategy_ret_after_cost.loc[trades] -= FEE_RATE
            nav = (1.0 + strategy_ret_after_cost).cumprod()

            daily = pd.DataFrame(
                {
                    "date": close.index,
                    "window_label": label,
                    "lookback_days": lookback_days,
                    "position": positions.values,
                    "strategy_return": strategy_ret.values,
                    "strategy_return_after_cost": strategy_ret_after_cost.values,
                    "trade": trades.values,
                    "nav": nav.values,
                }
            )

            metrics = calc_metrics(label, lookback_days, nav, strategy_ret_after_cost, positions, trades)
            return daily, decisions, metrics


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


        def calc_metrics(label: str, lookback_days: int, nav: pd.Series, ret: pd.Series, positions: pd.Series, trades: pd.Series) -> dict:
            return {
                "window_label": label,
                "lookback_days": lookback_days,
                "total_return": nav.iloc[-1] / nav.iloc[0] - 1.0,
                "annualized_return": annualized_return(nav),
                "annualized_volatility": annualized_volatility(ret),
                "max_drawdown": max_drawdown(nav),
                "sharpe_like_no_rf": sharpe_like(ret),
                "trade_count": int(trades.sum()),
                "cash_days": int(positions.eq("CASH").sum()),
                "defensive_days": int(positions.isin(defensive_symbols).sum()),
                "sector_days": int(positions.isin(sector_symbols).sum()),
                "final_nav": float(nav.iloc[-1]),
            }
        """
    ),
    md("""## 4. 跑 1~6 个月窗口并汇总"""),
    code(
        """
        all_daily = []
        all_decisions = []
        all_metrics = []

        for label, days in WINDOWS.items():
            daily, decisions, metrics = run_strategy_for_window(label, days)
            all_daily.append(daily)
            all_decisions.append(decisions)
            all_metrics.append(metrics)

        daily_all = pd.concat(all_daily, ignore_index=True)
        decisions_all = pd.concat(all_decisions, ignore_index=True)
        metrics = pd.DataFrame(all_metrics).sort_values("lookback_days")

        benchmark_symbol = "510300" if "510300" in close.columns else benchmark_symbols[0]
        benchmark_nav = (1.0 + daily_ret[benchmark_symbol]).cumprod()
        benchmark_metrics = pd.DataFrame(
            [
                {
                    "window_label": f"buy_hold_{benchmark_symbol}",
                    "lookback_days": 0,
                    "total_return": benchmark_nav.iloc[-1] / benchmark_nav.iloc[0] - 1.0,
                    "annualized_return": annualized_return(benchmark_nav),
                    "annualized_volatility": annualized_volatility(daily_ret[benchmark_symbol]),
                    "max_drawdown": max_drawdown(benchmark_nav),
                    "sharpe_like_no_rf": sharpe_like(daily_ret[benchmark_symbol]),
                    "trade_count": 0,
                    "cash_days": 0,
                    "defensive_days": 0,
                    "sector_days": len(benchmark_nav),
                    "final_nav": float(benchmark_nav.iloc[-1]),
                }
            ]
        )

        metrics_with_benchmark = pd.concat([metrics, benchmark_metrics], ignore_index=True)
        metrics_with_benchmark
        """
    ),
    md("""## 5. 关键指标排序"""),
    code(
        """
        display_cols = [
            "window_label",
            "lookback_days",
            "total_return",
            "annualized_return",
            "annualized_volatility",
            "max_drawdown",
            "sharpe_like_no_rf",
            "trade_count",
            "cash_days",
            "defensive_days",
            "sector_days",
        ]
        metrics[display_cols].sort_values("annualized_return", ascending=False)
        """
    ),
    code(
        """
        metrics[display_cols].sort_values("sharpe_like_no_rf", ascending=False)
        """
    ),
    md("""## 6. 最近调仓信号对比"""),
    code(
        """
        latest_decisions = decisions_all.sort_values(["signal_date", "lookback_days"]).groupby("window_label").tail(5)
        latest_decisions[[
            "window_label",
            "signal_date",
            "chosen_symbol",
            "chosen_name",
            "chosen_bucket",
            "selected_momentum",
            "best_sector_symbol",
            "best_sector_momentum",
            "best_defensive_symbol",
            "best_defensive_momentum",
            "reason",
        ]].tail(30)
        """
    ),
    md("""## 7. 保存 CSV 结果"""),
    code(
        """
        daily_path = OUTPUT_DIR / "etf_momentum_1to6_month_comparison_daily.csv"
        decisions_path = OUTPUT_DIR / "etf_momentum_1to6_month_comparison_decisions.csv"
        metrics_path = OUTPUT_DIR / "etf_momentum_1to6_month_comparison_metrics.csv"

        daily_all.to_csv(daily_path, index=False, encoding="utf-8-sig")
        decisions_all.to_csv(decisions_path, index=False, encoding="utf-8-sig")
        metrics_with_benchmark.to_csv(metrics_path, index=False, encoding="utf-8-sig")

        print(f"已保存每日净值: {daily_path}")
        print(f"已保存调仓决策: {decisions_path}")
        print(f"已保存绩效指标: {metrics_path}")
        """
    ),
    md(
        """
        ## 8. 解读提醒

        短窗口和长窗口的差别，本质是：

        - **短窗口**：反应更快，但更容易被短期反弹/噪音骗进去，换仓可能更多；
        - **长窗口**：更稳，但确认趋势慢，可能在拐点处滞后。

        不要只看年化收益，要同时看：

        1. 最大回撤；
        2. 年化波动；
        3. 换仓次数；
        4. 防守/空仓天数；
        5. 不同市场阶段表现。

        如果某个窗口只在当前样本中最好，但换仓很多、回撤没有改善，那未必更可靠。
        """
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NOTEBOOK_PATH.parent.mkdir(parents=True, exist_ok=True)
NOTEBOOK_PATH.write_text(json.dumps(notebook, ensure_ascii=False, indent=2), encoding="utf-8")
print(NOTEBOOK_PATH)
