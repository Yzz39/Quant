from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Bar:
    open: float | None
    close: float | None
    can_buy: bool = True
    can_sell: bool = True
    cash_dividend: float = 0.0
    split_ratio: float = 1.0


@dataclass
class PendingRebalance:
    signal_date: str
    target_weights: dict[str, float]
    remaining_shares: dict[str, int] | None = None
    attempts: int = 0


@dataclass(frozen=True)
class OrderRecord:
    signal_date: str
    order_date: str
    symbol: str
    side: str
    requested_shares: int
    filled_shares: int
    raw_open: float | None
    fill_price: float | None
    gross_value: float
    fee: float
    status: str
    reason: str = ""


@dataclass(frozen=True)
class DailyRecord:
    date: str
    cash: float
    positions_value: float
    total_value: float
    positions: dict[str, int]


@dataclass
class AccountingEngine:
    initial_cash: float = 100_000.0
    commission_rate: float = 0.0002
    minimum_commission: float = 5.0
    slippage_rate: float = 0.0005
    lot_size: int = 100
    max_retry_days: int = 3
    cash: float = field(init=False)
    positions: dict[str, int] = field(default_factory=dict, init=False)
    last_prices: dict[str, float] = field(default_factory=dict, init=False)
    pending: PendingRebalance | None = field(default=None, init=False)
    orders: list[OrderRecord] = field(default_factory=list, init=False)
    daily: list[DailyRecord] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        if self.lot_size <= 0 or self.max_retry_days <= 0:
            raise ValueError("lot_size and max_retry_days must be positive")
        self.cash = float(self.initial_cash)

    def submit_signal(self, signal_date: str, target_weights: Mapping[str, float]) -> None:
        if self.pending is not None:
            raise RuntimeError("an earlier rebalance is still pending")
        weights = {str(symbol): float(weight) for symbol, weight in target_weights.items()}
        if any((not isfinite(weight)) or weight < 0 for weight in weights.values()):
            raise ValueError("target weights must be finite and non-negative")
        if sum(weights.values()) > 1.0 + 1e-12:
            raise ValueError("target weights cannot exceed 100%")
        self.pending = PendingRebalance(signal_date=signal_date, target_weights=weights)

    def process_day(self, date: str, bars: Mapping[str, Bar]) -> DailyRecord:
        self._apply_corporate_actions(bars)
        self._mark_open_prices(bars)

        if self.pending is not None and date > self.pending.signal_date:
            self._execute_pending(date, bars)

        self._mark_close_prices(bars)
        positions_value = self._positions_value()
        record = DailyRecord(
            date=date,
            cash=self.cash,
            positions_value=positions_value,
            total_value=self.cash + positions_value,
            positions=dict(self.positions),
        )
        self.daily.append(record)
        return record

    def _apply_corporate_actions(self, bars: Mapping[str, Bar]) -> None:
        for symbol, shares in list(self.positions.items()):
            bar = bars.get(symbol)
            if bar is None:
                continue
            if bar.split_ratio <= 0:
                raise ValueError("split_ratio must be positive")
            if bar.split_ratio != 1.0:
                adjusted = shares * bar.split_ratio
                rounded = round(adjusted)
                if abs(adjusted - rounded) > 1e-9:
                    raise ValueError("synthetic split must produce whole shares")
                self.positions[symbol] = int(rounded)
                shares = int(rounded)
            if bar.cash_dividend:
                self.cash += shares * bar.cash_dividend

    def _mark_open_prices(self, bars: Mapping[str, Bar]) -> None:
        for symbol, bar in bars.items():
            if self._valid_price(bar.open):
                self.last_prices[symbol] = float(bar.open)

    def _mark_close_prices(self, bars: Mapping[str, Bar]) -> None:
        for symbol, bar in bars.items():
            if self._valid_price(bar.close):
                self.last_prices[symbol] = float(bar.close)

    def _execute_pending(self, date: str, bars: Mapping[str, Bar]) -> None:
        assert self.pending is not None
        pending = self.pending
        if pending.remaining_shares is None:
            pending.remaining_shares = self._build_share_intents(pending.target_weights, bars)

        pending.attempts += 1
        self._execute_sells(date, bars, pending)
        self._execute_buys(date, bars, pending)

        remaining = {symbol: amount for symbol, amount in pending.remaining_shares.items() if amount}
        pending.remaining_shares = remaining
        if not remaining:
            self.pending = None
            return

        if pending.attempts >= self.max_retry_days:
            for symbol, amount in sorted(remaining.items()):
                self.orders.append(
                    OrderRecord(
                        signal_date=pending.signal_date,
                        order_date=date,
                        symbol=symbol,
                        side="buy" if amount > 0 else "sell",
                        requested_shares=abs(amount),
                        filled_shares=0,
                        raw_open=bars.get(symbol).open if bars.get(symbol) else None,
                        fill_price=None,
                        gross_value=0.0,
                        fee=0.0,
                        status="canceled",
                        reason="retry_limit",
                    )
                )
            self.pending = None

    def _build_share_intents(
        self, target_weights: Mapping[str, float], bars: Mapping[str, Bar]
    ) -> dict[str, int]:
        total_value = self.cash + self._positions_value()
        symbols = set(self.positions) | set(target_weights)
        intents: dict[str, int] = {}
        for symbol in sorted(symbols):
            target_weight = target_weights.get(symbol, 0.0)
            bar = bars.get(symbol)
            price = bar.open if bar is not None and self._valid_price(bar.open) else self.last_prices.get(symbol)
            if target_weight > 0 and not self._valid_price(price):
                target_shares = 0
            elif target_weight > 0:
                target_shares = self._round_lot_down(total_value * target_weight / float(price))
            else:
                target_shares = 0
            intents[symbol] = target_shares - self.positions.get(symbol, 0)
        return intents

    def _execute_sells(
        self, date: str, bars: Mapping[str, Bar], pending: PendingRebalance
    ) -> None:
        assert pending.remaining_shares is not None
        for symbol in sorted(pending.remaining_shares):
            amount = pending.remaining_shares[symbol]
            if amount >= 0:
                continue
            requested = min(-amount, self.positions.get(symbol, 0))
            bar = bars.get(symbol)
            if requested <= 0:
                pending.remaining_shares[symbol] = 0
                continue
            if bar is None or not self._valid_price(bar.open):
                self._record_blocked(pending, date, symbol, "sell", requested, bar, "missing_open")
                continue
            if not bar.can_sell:
                self._record_blocked(pending, date, symbol, "sell", requested, bar, "sell_blocked")
                continue

            fill_price = float(bar.open) * (1.0 - self.slippage_rate)
            gross = requested * fill_price
            fee = self._commission(gross)
            self.cash += gross - fee
            self.positions[symbol] -= requested
            if self.positions[symbol] == 0:
                del self.positions[symbol]
            pending.remaining_shares[symbol] += requested
            self.orders.append(
                OrderRecord(
                    signal_date=pending.signal_date,
                    order_date=date,
                    symbol=symbol,
                    side="sell",
                    requested_shares=requested,
                    filled_shares=requested,
                    raw_open=float(bar.open),
                    fill_price=fill_price,
                    gross_value=gross,
                    fee=fee,
                    status="filled",
                )
            )

    def _execute_buys(
        self, date: str, bars: Mapping[str, Bar], pending: PendingRebalance
    ) -> None:
        assert pending.remaining_shares is not None
        has_remaining_sell = any(amount < 0 for amount in pending.remaining_shares.values())
        for symbol in sorted(pending.remaining_shares):
            amount = pending.remaining_shares[symbol]
            if amount <= 0:
                continue
            bar = bars.get(symbol)
            if bar is None or not self._valid_price(bar.open):
                self._record_blocked(pending, date, symbol, "buy", amount, bar, "missing_open")
                continue
            if not bar.can_buy:
                self._record_blocked(pending, date, symbol, "buy", amount, bar, "buy_blocked")
                continue

            fill_price = float(bar.open) * (1.0 + self.slippage_rate)
            affordable = self._affordable_shares(fill_price)
            fill_shares = min(amount, affordable)
            if fill_shares <= 0:
                if has_remaining_sell:
                    self._record_blocked(
                        pending, date, symbol, "buy", amount, bar, "waiting_for_sell_cash"
                    )
                else:
                    pending.remaining_shares[symbol] = 0
                    self._record_blocked(
                        pending, date, symbol, "buy", amount, bar, "insufficient_cash", "canceled"
                    )
                continue

            gross = fill_shares * fill_price
            fee = self._commission(gross)
            self.cash -= gross + fee
            if self.cash < -1e-8:
                raise AssertionError("cash became negative")
            if abs(self.cash) < 1e-10:
                self.cash = 0.0
            self.positions[symbol] = self.positions.get(symbol, 0) + fill_shares
            pending.remaining_shares[symbol] -= fill_shares
            self.orders.append(
                OrderRecord(
                    signal_date=pending.signal_date,
                    order_date=date,
                    symbol=symbol,
                    side="buy",
                    requested_shares=amount,
                    filled_shares=fill_shares,
                    raw_open=float(bar.open),
                    fill_price=fill_price,
                    gross_value=gross,
                    fee=fee,
                    status="filled" if fill_shares == amount else "partial",
                    reason="" if fill_shares == amount else "cash_limited",
                )
            )
            if pending.remaining_shares[symbol] > 0 and not has_remaining_sell:
                pending.remaining_shares[symbol] = 0

    def _record_blocked(
        self,
        pending: PendingRebalance,
        date: str,
        symbol: str,
        side: str,
        requested: int,
        bar: Bar | None,
        reason: str,
        status: str = "blocked",
    ) -> None:
        self.orders.append(
            OrderRecord(
                signal_date=pending.signal_date,
                order_date=date,
                symbol=symbol,
                side=side,
                requested_shares=requested,
                filled_shares=0,
                raw_open=bar.open if bar else None,
                fill_price=None,
                gross_value=0.0,
                fee=0.0,
                status=status,
                reason=reason,
            )
        )

    def _affordable_shares(self, fill_price: float) -> int:
        if self.cash <= self.minimum_commission:
            return 0
        estimate = self._round_lot_down(self.cash / (fill_price * (1 + self.commission_rate)))
        while estimate > 0:
            gross = estimate * fill_price
            if gross + self._commission(gross) <= self.cash + 1e-9:
                return estimate
            estimate -= self.lot_size
        return 0

    def _positions_value(self) -> float:
        total = 0.0
        for symbol, shares in self.positions.items():
            if symbol not in self.last_prices:
                raise ValueError(f"missing mark price for held symbol {symbol}")
            total += shares * self.last_prices[symbol]
        return total

    def _commission(self, gross: float) -> float:
        if gross <= 0:
            return 0.0
        return max(self.minimum_commission, gross * self.commission_rate)

    def _round_lot_down(self, shares: float) -> int:
        return int(floor(shares / self.lot_size) * self.lot_size)

    @staticmethod
    def _valid_price(value: float | None) -> bool:
        return value is not None and isfinite(value) and value > 0
