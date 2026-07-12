"""Pure Python helpers for the Step 04 preregistered baseline."""

import math


def momentum_score(closes, lookback=126):
    values = list(closes)
    if lookback <= 0 or len(values) < lookback + 1:
        raise ValueError("not enough prices for the requested lookback")
    start = float(values[-lookback - 1])
    end = float(values[-1])
    if start <= 0 or end <= 0:
        raise ValueError("prices must be positive")
    return end / start - 1.0


def ols_slope_r2_score(closes, lookback=126):
    """Return the preregistered M3A log-price OLS slope-quality score."""
    values = [float(value) for value in closes]
    if lookback <= 0 or len(values) < lookback + 1:
        raise ValueError("not enough prices for the requested lookback")
    values = values[-lookback - 1 :]
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("prices must be finite and positive")

    y = [math.log(value) for value in values]
    n = len(y)
    x_mean = (n - 1) / 2.0
    y_mean = sum(y) / n
    denominator = sum((index - x_mean) ** 2 for index in range(n))
    beta = sum(
        (index - x_mean) * (value - y_mean) for index, value in enumerate(y)
    ) / denominator
    intercept = y_mean - beta * x_mean
    ss_res = sum(
        (value - (intercept + beta * index)) ** 2
        for index, value in enumerate(y)
    )
    ss_tot = sum((value - y_mean) ** 2 for value in y)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    r_squared = max(0.0, min(1.0, r_squared))
    return {"beta": beta, "r_squared": r_squared, "score": beta * r_squared}


def efficiency_momentum_score(closes, lookback=126):
    """Return log path return times Kaufman's path-efficiency ratio."""
    values = [float(value) for value in closes]
    if lookback <= 0 or len(values) < lookback + 1:
        raise ValueError("not enough prices for the requested lookback")
    values = values[-lookback - 1 :]
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("prices must be finite and positive")

    log_prices = [math.log(value) for value in values]
    path_return = log_prices[-1] - log_prices[0]
    path_length = sum(
        abs(log_prices[index] - log_prices[index - 1])
        for index in range(1, len(log_prices))
    )
    efficiency_ratio = abs(path_return) / path_length if path_length > 0 else 0.0
    efficiency_ratio = max(0.0, min(1.0, efficiency_ratio))
    return {
        "path_return": path_return,
        "efficiency_ratio": efficiency_ratio,
        "score": path_return * efficiency_ratio,
    }


def rank_momentum(scores):
    """Return (security, score) pairs, with a deterministic code tie-break."""
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def trend_outcome(prices, round_trip_cost=0.0014, min_net_return=0.01, max_mae=-0.05):
    """Evaluate the frozen 21-trading-day trend label on a price path."""
    values = [float(value) for value in prices]
    if len(values) < 2:
        raise ValueError("a trend path needs at least two prices")
    if any(value <= 0 for value in values):
        raise ValueError("prices must be positive")
    gross = values[-1] / values[0] - 1.0
    net = gross - round_trip_cost
    mae = min(value / values[0] - 1.0 for value in values)
    success = net >= min_net_return and mae >= max_mae
    return {
        "gross_return": gross,
        "net_return": net,
        "mae": mae,
        "success": success,
    }


def top1_gap(scores):
    ranked = rank_momentum(scores)
    if len(ranked) < 2:
        return ranked[0][1] if ranked else 0.0
    return ranked[0][1] - ranked[1][1]


def safe_buy_target_value(
    available_cash,
    current_value,
    desired_value,
    commission_rate=0.0002,
    slippage_rate=0.0005,
    minimum_commission=5.0,
):
    """Cap a target so costs cannot make cash negative after a buy."""
    incremental = max(float(desired_value) - float(current_value), 0.0)
    cash_after_minimum = max(float(available_cash) - minimum_commission, 0.0)
    max_incremental = cash_after_minimum / (1.0 + commission_rate + slippage_rate)
    return float(current_value) + min(incremental, max_incremental)


def absolute_momentum_target(scores, cash_security):
    """Apply M1: keep Top1 only when its own momentum is positive."""
    ranked = rank_momentum(scores)
    if not ranked:
        return {"selected": None, "absolute_pass": None, "decision": "no_eligible_asset", "target": {}}
    selected, score = ranked[0]
    if score > 0.0:
        return {
            "selected": selected,
            "absolute_pass": True,
            "decision": "top1",
            "target": {selected: 1.0},
        }
    if cash_security in scores:
        return {
            "selected": selected,
            "absolute_pass": False,
            "decision": "cash_filter",
            "target": {cash_security: 1.0},
        }
    return {
        "selected": selected,
        "absolute_pass": False,
        "decision": "cash_unavailable",
        "target": {},
    }


def recent_confirmation_target(long_scores, recent_scores, cash_security):
    """Apply M2: Top1 needs positive long and recent momentum."""
    ranked = rank_momentum(long_scores)
    if not ranked:
        return {
            "selected": None,
            "absolute_pass": None,
            "recent_pass": None,
            "decision": "no_eligible_asset",
            "target": {},
        }
    selected, long_score = ranked[0]
    recent_score = recent_scores[selected]
    absolute_pass = long_score > 0.0
    recent_pass = recent_score > 0.0
    if selected == cash_security:
        decision = "cash_top1"
        target = {cash_security: 1.0}
    elif absolute_pass and recent_pass:
        decision = "top1"
        target = {selected: 1.0}
    elif cash_security in long_scores:
        decision = "recent_filter" if absolute_pass else "cash_filter"
        target = {cash_security: 1.0}
    else:
        decision = "cash_unavailable"
        target = {}
    return {
        "selected": selected,
        "absolute_pass": absolute_pass,
        "recent_pass": recent_pass,
        "decision": decision,
        "target": target,
    }
