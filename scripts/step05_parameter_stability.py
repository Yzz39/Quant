"""Frozen parameter-grid helpers for the Step 05 JoinQuant experiment."""


SIGNAL_MODES = (
    "momentum",
    "m1_absolute",
    "m2_recent_confirm",
    "m2_ranked_recent",
    "m3_ols_slope",
    "m3b_efficiency",
    "m3c_bias_trend",
    "m3d_wls_slope",
    "m3e_huber_slope",
    "m3f_equal_rank",
    "m3g_efficiency_rank",
)
MOMENTUM_LOOKBACKS = (252, 126, 63, 31, 14)
REBALANCE_INTERVALS = (20, 10, 5, 1)

RECENT_LOOKBACK_BY_MOMENTUM = {252: 42, 126: 21, 63: 11, 31: 5, 14: 2}
BIAS_MA_WINDOW_BY_MOMENTUM = {252: 180, 126: 90, 63: 45, 31: 22, 14: 10}
BIAS_TREND_POINTS_BY_MOMENTUM = {252: 50, 126: 25, 63: 13, 31: 6, 14: 3}


def scaled_windows(momentum_lookback):
    """Return the preregistered proportional subwindows for one main horizon."""
    if momentum_lookback not in MOMENTUM_LOOKBACKS:
        raise ValueError(f"unsupported momentum lookback: {momentum_lookback}")
    return {
        "recent_lookback": RECENT_LOOKBACK_BY_MOMENTUM[momentum_lookback],
        "bias_ma_window": BIAS_MA_WINDOW_BY_MOMENTUM[momentum_lookback],
        "bias_trend_points": BIAS_TREND_POINTS_BY_MOMENTUM[momentum_lookback],
    }


def parameter_grid():
    """Return all 11 x 5 x 4 preregistered runs in their frozen order."""
    return [
        {
            "run_mode": mode,
            "lookback": lookback,
            "rebalance_interval": interval,
        }
        for mode in SIGNAL_MODES
        for lookback in MOMENTUM_LOOKBACKS
        for interval in REBALANCE_INTERVALS
    ]


def is_rebalance_trade_day(trade_day_number, interval):
    """Return whether a one-based trading-day number is on the frozen phase."""
    if trade_day_number <= 0:
        raise ValueError("trade_day_number must be positive")
    if interval not in REBALANCE_INTERVALS:
        raise ValueError(f"unsupported rebalance interval: {interval}")
    return trade_day_number % interval == 0
