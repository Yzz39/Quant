from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

BASE = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = BASE / "notebooks" / "etf_momentum_defensive_or_cash.ipynb"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": dedent(text).strip().splitlines(keepends=True)}


def code(text: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": dedent(text).strip().splitlines(keepends=True)}


cells = [
    md(
        """
        # ETF 动量轮动：负动量时切换到防守资产或空仓

        这个 notebook 在现有 ETF 动量数据项目基础上，加入一个更稳健的风险控制规则：

        > 每月末计算行业/主题 ETF 的过去 6 个月动量。若最强行业 ETF 动量为正，则下月持有该 ETF；若最强行业 ETF 动量为负或不可用，则不追行业，改为持有防守资产；若防守资产也没有正动量，则空仓。

        注意：这是学习和研究用样例，不构成投资建议。真实交易还要考虑滑点、最小佣金、成交约束、跟踪误差和税费等问题。
        """
    ),
    md(
        """
        ## 1. 规则说明

        本 notebook 使用以下默认口径：

        - 数据文件：`../data/etf_momentum_daily_eastmoney_qfq.csv`
        - 价格：前复权收盘价 `close`
        - 行业轮动池：`bucket == 'sector'`
        - 防守资产池：`bucket == 'defensive'`，当前已成功下载的是 `511010 国债ETF`、`511260 十年国债ETF`
        - 调仓频率：月末生成信号，下一个交易日持仓，避免未来函数
        - 动量窗口：126 个交易日，约 6 个月
        - 交易成本：每次换仓按组合净值扣 `0.02%`，只是简化估计
        - 规则：
          1. 在每个调仓日，找过去 126 日收益最高的行业 ETF；
          2. 若它的动量 `> 0`，下期持有它；
          3. 若它的动量 `<= 0`，在防守资产里找过去 126 日收益最高者；
          4. 若最佳防守资产动量 `> 0`，下期持有该防守资产；
          5. 否则空仓，日收益记为 0。
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

        LOOKBACK_DAYS = 126
        FEE_RATE = 0.0002
        INITIAL_NAV = 1.0

        DATA_PATH
        """
    ),
    md("""## 2. 读取数据并构建价格宽表"""),
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

        close = df.pivot(index="date", columns="symbol", values="close").sort_index()
        daily_ret = close.pct_change(fill_method=None).fillna(0.0)

        sector_symbols = meta.loc[meta["bucket"].eq("sector"), "symbol"].tolist()
        defensive_symbols = meta.loc[meta["bucket"].eq("defensive"), "symbol"].tolist()
        benchmark_symbols = meta.loc[meta["bucket"].eq("benchmark"), "symbol"].tolist()

        print(f"数据区间: {close.index.min().date()} ~ {close.index.max().date()}")
        print(f"ETF 数量: {close.shape[1]}")
        print(f"行业/主题 ETF: {len(sector_symbols)}", sector_symbols)
        print(f"防守资产: {len(defensive_symbols)}", defensive_symbols)
        print(f"基准资产: {len(benchmark_symbols)}", benchmark_symbols)
        meta.sort_values(["bucket", "symbol"])
        """
    ),
    md("""## 3. 计算月末动量与下期持仓"""),
    code(
        """
        def month_end_trading_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
            return pd.Series(index, index=index).groupby(index.to_period("M")).last().values


        rebalance_dates = pd.DatetimeIndex(month_end_trading_dates(close.index))
        momentum = close / close.shift(LOOKBACK_DAYS) - 1.0

        decisions = []
        for signal_date in rebalance_dates:
            if signal_date not in momentum.index:
                continue
            row = momentum.loc[signal_date]
            sector_mom = row[sector_symbols].dropna().sort_values(ascending=False)
            defensive_mom = row[defensive_symbols].dropna().sort_values(ascending=False)

            chosen_symbol = "CASH"
            chosen_bucket = "cash"
            chosen_name = "空仓"
            chosen_theme = "现金"
            reason = "行业动量不可用，且防守资产动量不可用，空仓"
            selected_momentum = np.nan
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
            else:
                selected_momentum = 0.0
                reason = "最佳行业/主题 ETF 动量为负或不可用，防守资产也无正动量，空仓"

            if chosen_symbol != "CASH":
                meta_row = meta.set_index("symbol").loc[chosen_symbol]
                chosen_name = meta_row["name"]
                chosen_theme = meta_row["theme"]

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
        decisions.head(), decisions.tail()
        """
    ),
    md("""## 4. 生成每日持仓，计算策略净值"""),
    code(
        """
        positions = pd.Series("CASH", index=close.index, name="position", dtype="object")
        decision_by_date = decisions.set_index("signal_date")

        current_position = "CASH"
        for date in close.index:
            positions.loc[date] = current_position
            if date in decision_by_date.index:
                # 月末收盘后才能知道信号，因此从下一个交易日开始生效。
                current_position = decision_by_date.loc[date, "chosen_symbol"]

        strategy_ret = pd.Series(0.0, index=close.index, name="strategy_return")
        for symbol in close.columns:
            mask = positions.eq(symbol)
            strategy_ret.loc[mask] = daily_ret.loc[mask, symbol]

        # 换仓当天扣一次简化成本。现金和 ETF 之间切换也视为交易。
        trades = positions.ne(positions.shift(1)).fillna(False)
        trades.iloc[0] = False
        strategy_ret_after_cost = strategy_ret.copy()
        strategy_ret_after_cost.loc[trades] -= FEE_RATE

        strategy_nav = (1.0 + strategy_ret_after_cost).cumprod() * INITIAL_NAV
        result_daily = pd.DataFrame(
            {
                "date": close.index,
                "position": positions.values,
                "strategy_return": strategy_ret.values,
                "strategy_return_after_cost": strategy_ret_after_cost.values,
                "trade": trades.values,
                "nav": strategy_nav.values,
            }
        )

        result_daily.tail()
        """
    ),
    md("""## 5. 绩效指标与基准对比"""),
    code(
        """
        def max_drawdown(nav: pd.Series) -> float:
            peak = nav.cummax()
            dd = nav / peak - 1.0
            return float(dd.min())


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


        benchmark_symbol = "510300" if "510300" in close.columns else benchmark_symbols[0]
        benchmark_nav = (1.0 + daily_ret[benchmark_symbol]).cumprod()

        metrics = pd.DataFrame(
            [
                {
                    "name": "momentum_defensive_or_cash",
                    "total_return": strategy_nav.iloc[-1] / strategy_nav.iloc[0] - 1.0,
                    "annualized_return": annualized_return(strategy_nav),
                    "annualized_volatility": annualized_volatility(strategy_ret_after_cost),
                    "max_drawdown": max_drawdown(strategy_nav),
                    "sharpe_like_no_rf": sharpe_like(strategy_ret_after_cost),
                    "trade_count": int(trades.sum()),
                    "cash_days": int(positions.eq("CASH").sum()),
                    "defensive_days": int(positions.isin(defensive_symbols).sum()),
                    "sector_days": int(positions.isin(sector_symbols).sum()),
                },
                {
                    "name": f"buy_hold_{benchmark_symbol}",
                    "total_return": benchmark_nav.iloc[-1] / benchmark_nav.iloc[0] - 1.0,
                    "annualized_return": annualized_return(benchmark_nav),
                    "annualized_volatility": annualized_volatility(daily_ret[benchmark_symbol]),
                    "max_drawdown": max_drawdown(benchmark_nav),
                    "sharpe_like_no_rf": sharpe_like(daily_ret[benchmark_symbol]),
                    "trade_count": 0,
                    "cash_days": 0,
                    "defensive_days": 0,
                    "sector_days": len(benchmark_nav),
                },
            ]
        )

        metrics
        """
    ),
    md("""## 6. 查看调仓记录"""),
    code(
        """
        decisions_display = decisions.copy()
        for column in ["selected_momentum", "best_sector_momentum", "best_defensive_momentum"]:
            decisions_display[column] = decisions_display[column].map(lambda x: f"{x:.2%}" if pd.notna(x) else "")
        decisions_display.tail(20)
        """
    ),
    md("""## 7. 保存结果文件"""),
    code(
        """
        daily_path = OUTPUT_DIR / "etf_momentum_defensive_or_cash_daily.csv"
        decision_path = OUTPUT_DIR / "etf_momentum_defensive_or_cash_decisions.csv"
        metrics_path = OUTPUT_DIR / "etf_momentum_defensive_or_cash_metrics.csv"

        result_daily.to_csv(daily_path, index=False, encoding="utf-8-sig")
        decisions.to_csv(decision_path, index=False, encoding="utf-8-sig")
        metrics.to_csv(metrics_path, index=False, encoding="utf-8-sig")

        print(f"已保存每日净值: {daily_path}")
        print(f"已保存调仓决策: {decision_path}")
        print(f"已保存绩效指标: {metrics_path}")
        """
    ),
    md(
        """
        ## 8. 如何解读这个策略

        这个规则的重点不是“预测市场”，而是减少一个常见错误：

        > 当所有行业 ETF 都是负动量时，还强行选一个“跌得最少的行业”满仓。

        加入防守资产/空仓规则后，策略会承认“没有好机会”这种状态。  
        但它也有明显代价：

        - 可能错过 V 型反转初期；
        - 防守资产本身也有利率风险或跟踪误差；
        - 空仓规则可能降低长期暴露，牛市中容易跑输；
        - 6 个月动量窗口只是教学默认值，不是最优参数。

        后续可以继续做参数稳健性测试：3/6/9/12 个月动量、不同防守资产、是否允许防守资产负动量仍持有、不同交易成本等。
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
