# JoinQuant Step 03 platform probe. This is not a trading strategy.
from jqdata import *


CORE = ["510300.XSHG", "511010.XSHG", "518880.XSHG", "511880.XSHG"]
COMMISSION = 0.0002
SLIPPAGE = 0.0005


def initialize(context):
    set_benchmark("000300.XSHG")
    set_option("use_real_price", True)
    set_option("avoid_future_data", True)
    set_option("order_volume_ratio", 0.005)
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=COMMISSION,
            close_commission=COMMISSION,
            min_commission=5,
        ),
        type="fund",
    )
    set_slippage(PriceRelatedSlippage(SLIPPAGE), type="fund")

    g.day_number = 0
    g.pending = None
    g.signal_date = None
    g.trade_schema_logged = False
    g.plan = {
        1: {"510300.XSHG": 0.50},
        4: {"518880.XSHG": 0.50},
        7: {},
    }

    starting_cash = context.portfolio.starting_cash
    if abs(starting_cash - 100_000.0) > 0.01:
        log.error("S03_CAPITAL_MISMATCH expected=100000.00 actual=%.2f" % starting_cash)
    else:
        log.info("S03_CAPITAL expected=100000.00 actual=%.2f" % starting_cash)

    security_tables = {
        "etf": get_all_securities(["etf"], date=context.current_dt.date()),
        "fund": get_all_securities(["fund"], date=context.current_dt.date()),
    }
    for security in CORE:
        matched_type = None
        matched_row = None
        for query_type, table in security_tables.items():
            if security in table.index:
                matched_type = query_type
                matched_row = table.loc[security]
                break
        if matched_row is None:
            log.error("S03_METADATA_MISSING date=%s security=%s" % (context.current_dt, security))
        else:
            log.info(
                "S03_METADATA security=%s query_type=%s start_date=%s end_date=%s platform_type=%s"
                % (
                    security,
                    matched_type,
                    matched_row.start_date,
                    matched_row.end_date,
                    matched_row.type,
                )
            )

    run_daily(execute_sells, time="open", reference_security="510300.XSHG")
    run_daily(execute_buys, time="09:35", reference_security="510300.XSHG")
    run_daily(create_after_close_signal, time="after_close", reference_security="510300.XSHG")
    run_daily(audit_after_close, time="after_close", reference_security="510300.XSHG")


def create_after_close_signal(context):
    g.day_number += 1
    if g.day_number not in g.plan:
        return

    target = dict(g.plan[g.day_number])
    g.pending = target
    g.signal_date = context.current_dt.date()

    for security in CORE:
        frame = get_price(
            security,
            end_date=context.current_dt,
            count=2,
            frequency="1d",
            fields=["close"],
            fq="pre",
        )
        last_data_date = frame.index[-1] if len(frame) else None
        log.info(
            "S03_DATA signal_date=%s security=%s last_data_date=%s rows=%s"
            % (g.signal_date, security, last_data_date, len(frame))
        )

    log.info("S03_SIGNAL date=%s target=%s" % (g.signal_date, target))


def execute_sells(context):
    if not _pending_is_from_prior_day(context):
        return

    target = g.pending
    for security in list(context.portfolio.positions.keys()):
        if target.get(security, 0.0) > 0:
            continue
        if not _can_trade(security, "sell"):
            log.info("S03_BLOCK date=%s side=sell security=%s" % (context.current_dt, security))
            continue
        current = get_current_data()[security]
        reference_price = current.last_price
        order = order_target_value(security, 0)
        log.info(
            "S03_ORDER date=%s signal_date=%s side=sell security=%s day_open=%s reference_price=%s order=%s"
            % (context.current_dt, g.signal_date, security, current.day_open, reference_price, order)
        )


def execute_buys(context):
    if not _pending_is_from_prior_day(context):
        return

    target = g.pending
    total_value = context.portfolio.total_value
    for security in CORE:
        weight = target.get(security, 0.0)
        if weight <= 0:
            continue
        if not _can_trade(security, "buy"):
            log.info("S03_BLOCK date=%s side=buy security=%s" % (context.current_dt, security))
            continue
        current = get_current_data()[security]
        reference_price = current.last_price
        order = order_target_value(security, total_value * weight)
        log.info(
            "S03_ORDER date=%s signal_date=%s side=buy security=%s day_open=%s reference_price=%s target=%.2f order=%s"
            % (
                context.current_dt,
                g.signal_date,
                security,
                current.day_open,
                reference_price,
                total_value * weight,
                order,
            )
        )

    g.pending = None
    g.signal_date = None


def audit_after_close(context):
    orders = get_orders()
    trades = get_trades()
    for order_id, order in orders.items():
        log.info(
            "S03_ORDER_AUDIT date=%s id=%s security=%s action=%s amount=%s filled=%s price=%s status=%s"
            % (
                context.current_dt,
                order_id,
                order.security,
                _order_action(order),
                order.amount,
                order.filled,
                order.price,
                order.status,
            )
        )
    for trade_id, trade in trades.items():
        if not g.trade_schema_logged:
            fields = sorted(name for name in dir(trade) if not name.startswith("_"))
            log.info("S03_TRADE_SCHEMA fields=%s" % fields)
            g.trade_schema_logged = True
        order_id = getattr(trade, "order_id", None)
        related_order = orders.get(order_id) if order_id is not None else None
        amount = getattr(trade, "amount", 0)
        price = getattr(trade, "price", 0)
        money = getattr(trade, "money", abs(amount) * price)
        log.info(
            "S03_TRADE date=%s id=%s order_id=%s security=%s action=%s amount=%s price=%s money=%s"
            % (
                context.current_dt,
                trade_id,
                order_id,
                getattr(trade, "security", "unknown"),
                _order_action(related_order),
                amount,
                price,
                money,
            )
        )

    positions = {
        security: position.total_amount
        for security, position in context.portfolio.positions.items()
        if position.total_amount
    }
    identity_error = abs(
        context.portfolio.available_cash
        + context.portfolio.positions_value
        - context.portfolio.total_value
    )
    log.info(
        "S03_EOD date=%s cash=%.6f positions_value=%.6f total_value=%.6f identity_error=%.10f positions=%s"
        % (
            context.current_dt,
            context.portfolio.available_cash,
            context.portfolio.positions_value,
            context.portfolio.total_value,
            identity_error,
            positions,
        )
    )


def _pending_is_from_prior_day(context):
    if g.pending is None or g.signal_date is None:
        return False
    if context.current_dt.date() <= g.signal_date:
        log.error(
            "S03_FUTURE_GUARD execution=%s signal=%s" % (context.current_dt.date(), g.signal_date)
        )
        return False
    return True


def _can_trade(security, side):
    current = get_current_data()[security]
    day_open = current.day_open
    if current.paused or day_open is None or day_open != day_open or day_open <= 0:
        return False
    if (
        side == "buy"
        and current.high_limit is not None
        and current.high_limit == current.high_limit
        and day_open >= current.high_limit
    ):
        return False
    if (
        side == "sell"
        and current.low_limit is not None
        and current.low_limit == current.low_limit
        and day_open <= current.low_limit
    ):
        return False
    return True


def _order_action(order):
    if order is None:
        return "unknown"
    action = getattr(order, "action", None)
    if action is not None:
        return action
    side = getattr(order, "side", None)
    if side is not None:
        return side
    is_buy = getattr(order, "is_buy", None)
    if is_buy is True:
        return "buy"
    if is_buy is False:
        return "sell"
    return "unknown"
