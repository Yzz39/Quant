import pandas as pd

metrics_path = r"D:/Quant/outputs/etf_momentum_rebalance_frequency_comparison_metrics.csv"
daily_path = r"D:/Quant/outputs/etf_momentum_rebalance_frequency_comparison_daily.csv"
summary_path = r"D:/Quant/outputs/etf_momentum_rebalance_frequency_summary.csv"
metrics = pd.read_csv(metrics_path)
daily = pd.read_csv(daily_path, dtype={"previous_position": "string", "position": "string"}, low_memory=False)
summary = pd.read_csv(summary_path)
required_metrics = [
    "order_count",
    "total_one_way_turnover",
    "annual_one_way_turnover",
    "total_two_way_traded",
    "annual_two_way_traded",
    "total_estimated_cost",
    "annual_estimated_cost",
    "cost_drag",
    "final_nav_before_cost",
]
required_daily = ["previous_position", "one_way_turnover", "two_way_traded", "order_count", "estimated_cost", "nav_before_cost"]
print("missing_metrics_cols", [column for column in required_metrics if column not in metrics.columns])
print("missing_daily_cols", [column for column in required_daily if column not in daily.columns])
print("\nmetrics_sample_top5")
print(
    metrics[metrics["lookback_days"].gt(0)]
    .sort_values("annualized_return", ascending=False)[
        [
            "window_label",
            "rebalance_frequency",
            "annualized_return",
            "trade_count",
            "order_count",
            "total_one_way_turnover",
            "annual_one_way_turnover",
            "total_two_way_traded",
            "annual_two_way_traded",
            "total_estimated_cost",
            "cost_drag",
            "final_nav",
            "final_nav_before_cost",
        ]
    ]
    .head(5)
    .to_string(index=False)
)
print("\nfrequency_summary")
print(summary.to_string(index=False))
print("\ndaily_nonzero_turnover_sample")
print(
    daily[daily["one_way_turnover"].gt(0)][
        [
            "date",
            "window_label",
            "rebalance_frequency",
            "previous_position",
            "position",
            "one_way_turnover",
            "two_way_traded",
            "order_count",
            "estimated_cost",
        ]
    ]
    .head(10)
    .to_string(index=False)
)
combo = metrics[(metrics["window_label"].eq("mom_2m")) & (metrics["rebalance_frequency"].eq("biweekly"))].iloc[0]
sub = daily[(daily["window_label"].eq("mom_2m")) & (daily["rebalance_frequency"].eq("biweekly"))]
print("\nconsistency_mom_2m_biweekly")
print("metric_one_way", combo["total_one_way_turnover"], "daily_sum", sub["one_way_turnover"].sum())
print("metric_two_way", combo["total_two_way_traded"], "daily_sum", sub["two_way_traded"].sum())
print("metric_order_count", combo["order_count"], "daily_sum", sub["order_count"].sum())
print("metric_cost", combo["total_estimated_cost"], "daily_sum", sub["estimated_cost"].sum())
