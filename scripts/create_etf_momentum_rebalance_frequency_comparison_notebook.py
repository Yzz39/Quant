from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

BASE = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = BASE / "notebooks" / "etf_momentum_rebalance_frequency_comparison.ipynb"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(text).strip().splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": dedent(text).strip().splitlines(keepends=True)}


cells = [
    md(
        """
        # ETF 动量策略：调仓频率对收益率的影响

        这个 notebook 在 `1~6个月动量窗口 + 防守资产/空仓规则` 的基础上，进一步比较不同调仓频率对收益、回撤、波动和换仓次数的影响。

        核心问题：

        > 更频繁调仓到底提升了收益，还是只是增加交易成本和噪音？

        注意：这是学习和研究样例，不构成投资建议。
        """
    ),
    md(
        """
        ## 1. 对比设计

        动量窗口：

        | 窗口 | 交易日近似 |
        |---:|---:|
        | 1个月 | 21 |
        | 2个月 | 42 |
        | 3个月 | 63 |
        | 4个月 | 84 |
        | 5个月 | 105 |
        | 6个月 | 126 |

        调仓频率：

        | 频率 | 含义 |
        |---|---|
        | `weekly` | 每周最后一个交易日生成信号 |
        | `biweekly` | 每两周最后一个交易日生成信号 |
        | `monthly` | 每月最后一个交易日生成信号 |
        | `quarterly` | 每季度最后一个交易日生成信号 |

        其它规则保持一致：

        1. 调仓日收盘后计算信号，下一个交易日生效，避免未来函数；
        2. 行业/主题 ETF 中选 N 月动量最高者；
        3. 若最佳行业 ETF 动量为正，持有它；
        4. 若最佳行业 ETF 动量为负或不可用，转向防守资产；
        5. 若最佳防守资产动量也不为正，则空仓；
        6. 每次换仓扣 `0.02%` 简化成本。
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
        REBALANCE_FREQUENCIES = ["weekly", "biweekly", "monthly", "quarterly"]
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
        """
    ),
    md("""## 3. 调仓日与回测函数"""),
    code(
        """
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


        def run_strategy(label: str, lookback_days: int, frequency: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
            signal_dates = rebalance_dates_for_frequency(close.index, frequency)
            momentum = close / close.shift(lookback_days) - 1.0
            decisions = []

            for signal_date in signal_dates:
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
                        "rebalance_frequency": frequency,
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
                    "rebalance_frequency": frequency,
                    "position": positions.values,
                    "strategy_return": strategy_ret.values,
                    "strategy_return_after_cost": strategy_ret_after_cost.values,
                    "trade": trades.values,
                    "nav": nav.values,
                }
            )

            metrics = {
                "window_label": label,
                "lookback_days": lookback_days,
                "rebalance_frequency": frequency,
                "total_return": nav.iloc[-1] / nav.iloc[0] - 1.0,
                "annualized_return": annualized_return(nav),
                "annualized_volatility": annualized_volatility(strategy_ret_after_cost),
                "max_drawdown": max_drawdown(nav),
                "sharpe_like_no_rf": sharpe_like(strategy_ret_after_cost),
                "trade_count": int(trades.sum()),
                "cash_days": int(positions.eq("CASH").sum()),
                "defensive_days": int(positions.isin(defensive_symbols).sum()),
                "sector_days": int(positions.isin(sector_symbols).sum()),
                "final_nav": float(nav.iloc[-1]),
                "signal_count": len(decisions),
            }
            return daily, decisions, metrics
        """
    ),
    md("""## 4. 执行 24 组对比"""),
    code(
        """
        all_daily = []
        all_decisions = []
        all_metrics = []

        for label, days in WINDOWS.items():
            for frequency in REBALANCE_FREQUENCIES:
                daily, decisions, metrics = run_strategy(label, days, frequency)
                all_daily.append(daily)
                all_decisions.append(decisions)
                all_metrics.append(metrics)

        daily_all = pd.concat(all_daily, ignore_index=True)
        decisions_all = pd.concat(all_decisions, ignore_index=True)
        metrics = pd.DataFrame(all_metrics).sort_values(["lookback_days", "rebalance_frequency"])

        benchmark_symbol = "510300" if "510300" in close.columns else benchmark_symbols[0]
        benchmark_nav = (1.0 + daily_ret[benchmark_symbol]).cumprod()
        benchmark_metrics = pd.DataFrame(
            [
                {
                    "window_label": f"buy_hold_{benchmark_symbol}",
                    "lookback_days": 0,
                    "rebalance_frequency": "buy_hold",
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
                    "signal_count": 0,
                }
            ]
        )
        metrics_with_benchmark = pd.concat([metrics, benchmark_metrics], ignore_index=True)
        metrics_with_benchmark
        """
    ),
    md("""## 5. 对比：同一动量窗口下，不同调仓频率"""),
    code(
        """
        display_cols = [
            "window_label",
            "rebalance_frequency",
            "annualized_return",
            "max_drawdown",
            "sharpe_like_no_rf",
            "trade_count",
            "signal_count",
            "cash_days",
            "defensive_days",
            "final_nav",
        ]
        metrics[display_cols].sort_values(["window_label", "annualized_return"], ascending=[True, False])
        """
    ),
    md("""## 6. 对比：全组合排序"""),
    code(
        """
        metrics[display_cols].sort_values("annualized_return", ascending=False).head(12)
        """
    ),
    code(
        """
        metrics[display_cols].sort_values("sharpe_like_no_rf", ascending=False).head(12)
        """
    ),
    md("""## 7. 频率均值：不区分动量窗口"""),
    code(
        """
        frequency_summary = (
            metrics.groupby("rebalance_frequency")
            .agg(
                avg_annualized_return=("annualized_return", "mean"),
                median_annualized_return=("annualized_return", "median"),
                avg_max_drawdown=("max_drawdown", "mean"),
                avg_sharpe_like=("sharpe_like_no_rf", "mean"),
                avg_trade_count=("trade_count", "mean"),
                best_annualized_return=("annualized_return", "max"),
                worst_annualized_return=("annualized_return", "min"),
            )
            .sort_values("avg_annualized_return", ascending=False)
        )
        frequency_summary
        """
    ),
    md("""## 8. 保存结果"""),
    code(
        """
        daily_path = OUTPUT_DIR / "etf_momentum_rebalance_frequency_comparison_daily.csv"
        decisions_path = OUTPUT_DIR / "etf_momentum_rebalance_frequency_comparison_decisions.csv"
        metrics_path = OUTPUT_DIR / "etf_momentum_rebalance_frequency_comparison_metrics.csv"
        frequency_summary_path = OUTPUT_DIR / "etf_momentum_rebalance_frequency_summary.csv"

        daily_all.to_csv(daily_path, index=False, encoding="utf-8-sig")
        decisions_all.to_csv(decisions_path, index=False, encoding="utf-8-sig")
        metrics_with_benchmark.to_csv(metrics_path, index=False, encoding="utf-8-sig")
        frequency_summary.to_csv(frequency_summary_path, encoding="utf-8-sig")

        print(f"已保存每日净值: {daily_path}")
        print(f"已保存调仓决策: {decisions_path}")
        print(f"已保存绩效指标: {metrics_path}")
        print(f"已保存频率汇总: {frequency_summary_path}")
        """
    ),
    md(
        """
        ## 9. 解读提醒

        调仓频率不是越高越好：

        - 周调仓可能更快识别趋势变化，但也更容易吃到短期噪音；
        - 季调仓交易少，但可能错过拐点；
        - 月调仓通常是一个折中点；
        - 双周调仓可以作为周/月之间的中间方案。

        重点不要只看年化收益，也要看换仓次数、最大回撤和防守/空仓天数。  
        如果某个频率收益更高但换仓次数暴增，实盘里可能被滑点、冲击成本和最小佣金吞掉。
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
