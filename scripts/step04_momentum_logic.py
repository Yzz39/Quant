"""Pure Python helpers for the Step 04 preregistered baseline."""

import math


def _require_finite_outputs(name, **values):
    invalid = {
        key: value
        for key, value in values.items()
        if not math.isfinite(float(value))
    }
    if invalid:
        raise ValueError(f"{name} produced non-finite output: {invalid}")


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


def wls_slope_r2_score(closes, lookback=126):
    """Return the preregistered M3D linearly weighted log-price slope score."""
    values = [float(value) for value in closes]
    if lookback <= 0 or len(values) < lookback + 1:
        raise ValueError("not enough prices for the requested lookback")
    values = values[-lookback - 1 :]
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("prices must be finite and positive")

    y = [math.log(value) for value in values]
    n = len(y)
    weights = [1.0 + index / (n - 1) for index in range(n)]
    weight_sum = sum(weights)
    x_mean = sum(weight * index for index, weight in enumerate(weights)) / weight_sum
    y_mean = sum(weight * value for weight, value in zip(weights, y)) / weight_sum
    denominator = sum(
        weight * (index - x_mean) ** 2
        for index, weight in enumerate(weights)
    )
    beta = sum(
        weight * (index - x_mean) * (value - y_mean)
        for index, (weight, value) in enumerate(zip(weights, y))
    ) / denominator
    intercept = y_mean - beta * x_mean
    ss_res = sum(
        weight * (value - (intercept + beta * index)) ** 2
        for index, (weight, value) in enumerate(zip(weights, y))
    )
    ss_tot = sum(
        weight * (value - y_mean) ** 2
        for weight, value in zip(weights, y)
    )
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    r_squared = max(0.0, min(1.0, r_squared))
    return {"beta": beta, "r_squared": r_squared, "score": beta * r_squared}


def _median(values):
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("median requires at least one value")
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _weighted_line_fit(y, weights):
    weight_sum = sum(weights)
    x_mean = sum(weight * index for index, weight in enumerate(weights)) / weight_sum
    y_mean = sum(weight * value for weight, value in zip(weights, y)) / weight_sum
    denominator = sum(
        weight * (index - x_mean) ** 2
        for index, weight in enumerate(weights)
    )
    beta = sum(
        weight * (index - x_mean) * (value - y_mean)
        for index, (weight, value) in enumerate(zip(weights, y))
    ) / denominator
    return y_mean - beta * x_mean, beta


def huber_slope_r2_score(
    closes,
    lookback=126,
    epsilon=1.345,
    max_iterations=50,
    tolerance=1e-10,
):
    """Return the preregistered M3E Huber IRLS log-price slope score."""
    values = [float(value) for value in closes]
    if lookback <= 0 or len(values) < lookback + 1:
        raise ValueError("not enough prices for the requested lookback")
    values = values[-lookback - 1 :]
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("prices must be finite and positive")
    if epsilon <= 0 or max_iterations <= 0 or tolerance <= 0:
        raise ValueError("Huber parameters must be positive")

    y = [math.log(value) for value in values]
    weights = [1.0] * len(y)
    intercept, beta = _weighted_line_fit(y, weights)
    iterations = 0
    scale_floor = 1e-12
    for iteration in range(1, max_iterations + 1):
        residuals = [
            value - (intercept + beta * index)
            for index, value in enumerate(y)
        ]
        residual_median = _median(residuals)
        mad = _median(abs(residual - residual_median) for residual in residuals)
        scale = mad / 0.6744897501960817
        if scale <= scale_floor:
            break
        threshold = epsilon * scale
        weights = [
            1.0 if abs(residual) <= threshold else threshold / abs(residual)
            for residual in residuals
        ]
        new_intercept, new_beta = _weighted_line_fit(y, weights)
        iterations = iteration
        converged = max(
            abs(new_intercept - intercept), abs(new_beta - beta)
        ) <= tolerance
        intercept, beta = new_intercept, new_beta
        if converged:
            break

    residuals = [
        value - (intercept + beta * index)
        for index, value in enumerate(y)
    ]
    residual_median = _median(residuals)
    mad = _median(abs(residual - residual_median) for residual in residuals)
    scale = mad / 0.6744897501960817
    if scale > scale_floor:
        threshold = epsilon * scale
        weights = [
            1.0 if abs(residual) <= threshold else threshold / abs(residual)
            for residual in residuals
        ]
        intercept, beta = _weighted_line_fit(y, weights)
        residuals = [
            value - (intercept + beta * index)
            for index, value in enumerate(y)
        ]

    weight_sum = sum(weights)
    y_mean = sum(weight * value for weight, value in zip(weights, y)) / weight_sum
    ss_res = sum(weight * error**2 for weight, error in zip(weights, residuals))
    ss_tot = sum(
        weight * (value - y_mean) ** 2
        for weight, value in zip(weights, y)
    )
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    r_squared = max(0.0, min(1.0, r_squared))
    downweighted = sum(1 for weight in weights if weight < 1.0 - 1e-12)
    score = beta * r_squared
    _require_finite_outputs("Huber", beta=beta, r_squared=r_squared, score=score)
    return {
        "beta": beta,
        "r_squared": r_squared,
        "score": score,
        "iterations": iterations,
        "downweighted": downweighted,
    }


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
    score = path_return * efficiency_ratio
    _require_finite_outputs(
        "efficiency",
        path_return=path_return,
        efficiency_ratio=efficiency_ratio,
        score=score,
    )
    return {
        "path_return": path_return,
        "efficiency_ratio": efficiency_ratio,
        "score": score,
    }


def bias_trend_score(closes, lookback=126, ma_window=90, trend_points=25):
    """Return the preregistered M3C normalized price/MA trend slope."""
    values = [float(value) for value in closes]
    required = max(lookback + 1, ma_window + trend_points - 1)
    if lookback <= 0 or ma_window <= 0 or trend_points < 2 or len(values) < required:
        raise ValueError("not enough prices for the requested bias trend")
    values = values[-lookback - 1 :]
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("prices must be finite and positive")

    bias_values = []
    first_index = len(values) - trend_points
    for index in range(first_index, len(values)):
        ma_start = index - ma_window + 1
        moving_average = sum(values[ma_start : index + 1]) / ma_window
        bias_values.append(values[index] / moving_average)

    base_bias = bias_values[0]
    normalized = [value / base_bias for value in bias_values]
    if any(not math.isfinite(value) for value in normalized):
        raise ValueError("bias trend produced non-finite normalized values")
    n = len(normalized)
    x_mean = (n - 1) / 2.0
    y_mean = sum(normalized) / n
    denominator = sum((index - x_mean) ** 2 for index in range(n))
    slope = sum(
        (index - x_mean) * (value - y_mean)
        for index, value in enumerate(normalized)
    ) / denominator
    _require_finite_outputs("bias trend", score=slope)
    return {"bias_slope": slope, "score": slope}


def equal_rank_fusion(component_scores):
    """Return M3F centered equal-weight Borda scores and per-factor ranks."""
    factor_names = sorted(component_scores)
    if not factor_names:
        raise ValueError("rank fusion requires at least one factor")
    securities = sorted(component_scores[factor_names[0]])
    if not securities:
        raise ValueError("rank fusion requires at least one security")
    security_set = set(securities)
    ranks = {security: {} for security in securities}

    for factor in factor_names:
        values = component_scores[factor]
        if set(values) != security_set:
            raise ValueError("rank fusion factors must cover the same securities")
        if any(not math.isfinite(float(value)) for value in values.values()):
            raise ValueError("rank fusion scores must be finite")
        ranked = sorted(values.items(), key=lambda item: (-item[1], item[0]))
        for rank, (security, _) in enumerate(ranked, start=1):
            ranks[security][factor] = rank

    security_count = len(securities)
    if security_count == 1:
        return {"scores": {securities[0]: 0.0}, "ranks": ranks}
    denominator = float((security_count - 1) * len(factor_names))
    fused_scores = {
        security: sum(
            security_count + 1 - 2 * ranks[security][factor]
            for factor in factor_names
        )
        / denominator
        for security in securities
    }
    return {"scores": fused_scores, "ranks": ranks}


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


def ranked_recent_target(long_scores, recent_scores, cash_security):
    """Walk a factor ranking until a positive-score, positive-recent candidate passes."""
    ranked = rank_momentum(long_scores)
    excluded = []
    for rank, (security, long_score) in enumerate(ranked, start=1):
        if security == cash_security:
            return {
                "selected": security,
                "selected_rank": rank,
                "excluded": excluded,
                "decision": "cash_ranked",
                "target": {security: 1.0},
            }
        recent_score = recent_scores[security]
        if long_score > 0.0 and recent_score > 0.0:
            return {
                "selected": security,
                "selected_rank": rank,
                "excluded": excluded,
                "decision": "ranked_recent_pass",
                "target": {security: 1.0},
            }
        excluded.append(security)

    if cash_security in long_scores:
        cash_rank = next(
            rank
            for rank, (security, _) in enumerate(ranked, start=1)
            if security == cash_security
        )
        return {
            "selected": cash_security,
            "selected_rank": cash_rank,
            "excluded": excluded,
            "decision": "cash_fallback",
            "target": {cash_security: 1.0},
        }
    return {
        "selected": None,
        "selected_rank": None,
        "excluded": excluded,
        "decision": "cash_unavailable",
        "target": {},
    }
