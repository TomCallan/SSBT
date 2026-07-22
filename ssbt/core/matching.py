"""Order matching engine — simulates fills against bar or bid/ask data.

Matching rules:
  Bar events:
    MARKET → fill at bar open (signal received after previous bar close, fill next bar open)
    LIMIT buy → fill if bar low <= limit price
    LIMIT sell → fill if bar high >= limit price
    STOP buy → trigger if bar high >= stop, then fill at stop (or worse)
    STOP sell → trigger if bar low <= stop, then fill at stop (or worse)
  BidAsk events:
    MARKET buy → fill at ask
    MARKET sell → fill at bid
    LIMIT buy → fill if bid <= limit price
    LIMIT sell → fill if ask >= limit price

Slippage and commission are configurable callables.
"""

from __future__ import annotations

from collections.abc import Callable

from ssbt.core.events import (
    Bar,
    BidAsk,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Side,
)


def default_slippage(price: float, qty: float, side: Side) -> float:
    """Default: 1 bps slippage."""
    slip = price * 0.0001
    return slip if side == Side.BUY else -slip


def default_commission(price: float, qty: float) -> float:
    """Default: 1 bps commission on notional."""
    return price * qty * 0.0001


class MatchingEngine:
    """Holds pending orders, processes them against incoming market data events."""

    def __init__(
        self,
        slippage_fn: Callable[[float, float, Side], float] = default_slippage,
        commission_fn: Callable[[float, float], float] = default_commission,
    ):
        self._pending: list[Order] = []
        self._fills: list[Fill] = []
        self._next_order_id = 1
        self._slippage_fn = slippage_fn
        self._commission_fn = commission_fn

    @property
    def fills(self) -> list[Fill]:
        return self._fills

    @property
    def pending_orders(self) -> list[Order]:
        return self._pending

    def submit(self, order: Order) -> Order:
        """Register an order. Returns the order with assigned ID."""
        order.id = self._next_order_id
        self._next_order_id += 1
        self._pending.append(order)
        return order

    def process_bar(self, bar: Bar) -> list[Fill]:
        """Match pending orders against a bar. Returns fills generated this bar."""
        new_fills: list[Fill] = []
        remaining: list[Order] = []

        for order in self._pending:
            if order.symbol != bar.symbol:
                remaining.append(order)
                continue

            fill_price = None
            fill_qty = 0.0

            if order.type == OrderType.MARKET:
                # Market fills at bar open
                fill_price = bar.open
                fill_qty = order.qty - order.filled_qty

            elif order.type == OrderType.LIMIT:
                if order.side == Side.BUY and bar.low <= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty
                elif order.side == Side.SELL and bar.high >= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty

            elif order.type == OrderType.STOP:
                if order.side == Side.BUY and bar.high >= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty
                elif order.side == Side.SELL and bar.low <= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty

            if fill_price is not None and fill_qty > 0:
                slipped = fill_price + self._slippage_fn(fill_price, fill_qty, order.side)
                commission = self._commission_fn(slipped, fill_qty)
                order.filled_qty += fill_qty

                fill = Fill(
                    timestamp=bar.timestamp,
                    order_id=order.id,
                    symbol=order.symbol,
                    side=order.side,
                    qty=fill_qty,
                    price=slipped,
                    commission=commission,
                )
                new_fills.append(fill)
                self._fills.append(fill)

                if order.filled_qty >= order.qty:
                    order.status = OrderStatus.FILLED
                else:
                    order.status = OrderStatus.PARTIALLY_FILLED
                    remaining.append(order)
            else:
                remaining.append(order)

        self._pending = remaining
        return new_fills

    def process_bidask(self, ba: BidAsk) -> list[Fill]:
        """Match pending orders against a bid/ask quote."""
        new_fills: list[Fill] = []
        remaining: list[Order] = []

        for order in self._pending:
            if order.symbol != ba.symbol:
                remaining.append(order)
                continue

            fill_price = None
            fill_qty = 0.0

            if order.type == OrderType.MARKET:
                fill_price = ba.ask if order.side == Side.BUY else ba.bid
                fill_qty = order.qty - order.filled_qty

            elif order.type == OrderType.LIMIT:
                if order.side == Side.BUY and ba.bid <= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty
                elif order.side == Side.SELL and ba.ask >= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty

            elif order.type == OrderType.STOP:
                if order.side == Side.BUY and ba.ask >= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty
                elif order.side == Side.SELL and ba.bid <= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty

            if fill_price is not None and fill_qty > 0:
                slipped = fill_price + self._slippage_fn(fill_price, fill_qty, order.side)
                commission = self._commission_fn(slipped, fill_qty)
                order.filled_qty += fill_qty

                fill = Fill(
                    timestamp=ba.timestamp,
                    order_id=order.id,
                    symbol=order.symbol,
                    side=order.side,
                    qty=fill_qty,
                    price=slipped,
                    commission=commission,
                )
                new_fills.append(fill)
                self._fills.append(fill)

                if order.filled_qty >= order.qty:
                    order.status = OrderStatus.FILLED
                else:
                    order.status = OrderStatus.PARTIALLY_FILLED
                    remaining.append(order)
            else:
                remaining.append(order)

        self._pending = remaining
        return new_fills

    def cancel(self, order_id: int) -> bool:
        """Cancel a pending order by ID. Returns True if cancelled."""
        for i, order in enumerate(self._pending):
            if order.id == order_id:
                order.status = OrderStatus.CANCELLED
                self._pending.pop(i)
                return True
        return False
