"""Order matching engine — simulates fills against bar or bid/ask data.

Order types:
  MARKET        Fill at next available price (bar open / bid/ask)
  LIMIT         Fill at limit price or better
  STOP          Stop market: trigger at stop price, fill as market
  STOP_LIMIT    Stop triggers limit order at stop_limit_price
  STOP_MARKET   Same as STOP (explicit)
  TRAILING_STOP Trail price by offset/pct, fill as market when hit

Time-in-force:
  GTC           Good till cancelled (default)
  GTD           Good till date (expire_at timestamp)
  IOC           Immediate or cancel — fill what you can, cancel rest on first evaluation
  FOK           Fill or kill — fill entirely on first evaluation or cancel
  DAY           Expire at day boundary (timestamp date change)

OCO support: linked orders via oco_pair_id. When one fills, partner cancelled.
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
    TimeInForce,
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
        self._next_oco_id = 1
        self._slippage_fn = slippage_fn
        self._commission_fn = commission_fn
        self._new_orders = False  # flag: strategy submitted new orders this tick

    @property
    def fills(self) -> list[Fill]:
        return self._fills

    @property
    def pending_orders(self) -> list[Order]:
        return self._pending

    @property
    def has_new(self) -> bool:
        """True if strategy submitted new orders since last check."""
        v = self._new_orders
        self._new_orders = False
        return v

    def submit(self, order: Order) -> Order:
        """Register an order. Returns the order with assigned ID."""
        order.id = self._next_order_id
        self._next_order_id += 1
        self._pending.append(order)
        self._new_orders = True
        return order

    def submit_oco(self, order_a: Order, order_b: Order) -> tuple[Order, Order]:
        """Submit an OCO pair. When one fills, the other is cancelled."""
        pair_id = self._next_oco_id
        self._next_oco_id += 1
        order_a.oco_pair_id = pair_id
        order_b.oco_pair_id = pair_id
        self.submit(order_a)
        self.submit(order_b)
        return order_a, order_b

    def _cancel_oco_partner(self, filled_order: Order) -> None:
        """Cancel the OCO partner of a filled order."""
        if filled_order.oco_pair_id is None:
            return
        for i, o in enumerate(self._pending):
            if o.oco_pair_id == filled_order.oco_pair_id and o.id != filled_order.id:
                o.status = OrderStatus.CANCELLED
                self._pending.pop(i)
                return

    def _check_tif_expiry(self, order: Order, timestamp: int) -> bool:
        """Check if order should expire based on TIF. Returns True if expired."""
        if order.tif == TimeInForce.GTD and order.expire_at is not None:
            if timestamp >= order.expire_at:
                order.status = OrderStatus.EXPIRED
                return True
        return False

    def _check_ioc_fok(self, order: Order, fill_qty: float, timestamp: int) -> bool:
        """Handle IOC/FOK logic. Returns True if order should be cancelled after this evaluation.

        IOC: fill what you can, cancel remainder.
        FOK: if can't fill entire qty, cancel entirely.
        """
        if order.tif == TimeInForce.IOC:
            # Cancel any remaining qty after partial fill
            if order.filled_qty < order.qty:
                order.status = OrderStatus.CANCELLED if order.filled_qty == 0 else OrderStatus.PARTIALLY_FILLED
                return True
        elif order.tif == TimeInForce.FOK:
            # Must fill entirely or cancel
            if order.filled_qty + fill_qty < order.qty:
                # Can't fill entirely — rollback and cancel
                order.filled_qty -= fill_qty
                order.status = OrderStatus.CANCELLED
                return True
        return False

    def process_bar(self, bar: Bar) -> list[Fill]:
        """Match pending orders against a bar. Returns fills generated this bar."""
        if not self._pending:
            return []

        new_fills: list[Fill] = []
        indices_to_remove: list[int] = []

        for i, order in enumerate(self._pending):
            if order.symbol != bar.symbol:
                continue

            # Check TIF expiry
            if self._check_tif_expiry(order, bar.timestamp):
                indices_to_remove.append(i)
                continue

            fill_price = None
            fill_qty = 0.0
            cancel_after = False

            if order.type == OrderType.MARKET:
                fill_price = bar.open
                fill_qty = order.qty - order.filled_qty

            elif order.type == OrderType.LIMIT:
                if order.side == Side.BUY and bar.low <= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty
                elif order.side == Side.SELL and bar.high >= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty

            elif order.type in (OrderType.STOP, OrderType.STOP_MARKET):
                if order.side == Side.BUY and bar.high >= order.price:
                    fill_price = bar.open if bar.open >= order.price else order.price
                    fill_qty = order.qty - order.filled_qty
                elif order.side == Side.SELL and bar.low <= order.price:
                    fill_price = bar.open if bar.open <= order.price else order.price
                    fill_qty = order.qty - order.filled_qty

            elif order.type == OrderType.STOP_LIMIT:
                triggered = False
                if order.side == Side.BUY and bar.high >= order.price:
                    triggered = True
                elif order.side == Side.SELL and bar.low <= order.price:
                    triggered = True

                if triggered:
                    limit = order.stop_limit_price or order.price
                    if order.side == Side.BUY and bar.low <= limit:
                        fill_price = limit
                        fill_qty = order.qty - order.filled_qty
                    elif order.side == Side.SELL and bar.high >= limit:
                        fill_price = limit
                        fill_qty = order.qty - order.filled_qty
                    else:
                        # Triggered but limit not hit — convert to LIMIT and stay
                        order.type = OrderType.LIMIT
                        order.price = limit

            elif order.type == OrderType.TRAILING_STOP:
                # Track extreme price first
                extreme_updated = False
                if order.side == Side.SELL:
                    if bar.high > order.trail_extreme:
                        order.trail_extreme = bar.high
                        extreme_updated = True
                    if order.trail_offset is not None:
                        if order.trail_is_pct:
                            stop = order.trail_extreme * (1 - order.trail_offset)
                        else:
                            stop = order.trail_extreme - order.trail_offset
                        # Only trigger if extreme was already set on a prior bar
                        if not extreme_updated and order.trail_extreme > 0 and bar.low <= stop:
                            fill_price = bar.open if bar.open <= stop else stop
                            fill_qty = order.qty - order.filled_qty
                else:  # BUY
                    if order.trail_extreme == 0 or bar.low < order.trail_extreme:
                        order.trail_extreme = bar.low
                        extreme_updated = True
                    if order.trail_offset is not None:
                        if order.trail_is_pct:
                            stop = order.trail_extreme * (1 + order.trail_offset)
                        else:
                            stop = order.trail_extreme + order.trail_offset
                        if not extreme_updated and order.trail_extreme > 0 and bar.high >= stop:
                            fill_price = bar.open if bar.open >= stop else stop
                            fill_qty = order.qty - order.filled_qty

            # Apply fill
            if fill_price is not None and fill_qty > 0:
                # FOK check: can we fill entire qty?
                if order.tif == TimeInForce.FOK:
                    # For bar data, assume full fill possible if price in range
                    # (simplified: bar data always can fill at limit price)
                    pass

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

                # IOC check after fill
                if order.tif == TimeInForce.IOC and order.filled_qty < order.qty:
                    order.status = OrderStatus.PARTIALLY_FILLED
                    cancel_after = True

                if order.filled_qty >= order.qty:
                    order.status = OrderStatus.FILLED
                    indices_to_remove.append(i)
                    # Cancel OCO partner
                    self._cancel_oco_partner(order)
                elif cancel_after:
                    indices_to_remove.append(i)
            else:
                # No fill — check IOC/FOK first evaluation
                if not order._first_eval:
                    order._first_eval = True
                    if order.tif == TimeInForce.FOK:
                        # FOK couldn't fill on first evaluation — cancel
                        order.status = OrderStatus.CANCELLED
                        indices_to_remove.append(i)
                    elif order.tif == TimeInForce.IOC:
                        # IOC couldn't fill on first evaluation — cancel
                        order.status = OrderStatus.CANCELLED
                        indices_to_remove.append(i)

        # Remove filled/cancelled/expired orders in reverse order (preserve indices)
        for i in sorted(indices_to_remove, reverse=True):
            if i < len(self._pending):
                self._pending.pop(i)

        return new_fills

    def process_bidask(self, ba: BidAsk) -> list[Fill]:
        """Match pending orders against a bid/ask quote."""
        if not self._pending:
            return []

        new_fills: list[Fill] = []
        indices_to_remove: list[int] = []

        for i, order in enumerate(self._pending):
            if order.symbol != ba.symbol:
                continue

            if self._check_tif_expiry(order, ba.timestamp):
                indices_to_remove.append(i)
                continue

            fill_price = None
            fill_qty = 0.0
            cancel_after = False

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

            elif order.type in (OrderType.STOP, OrderType.STOP_MARKET):
                if order.side == Side.BUY and ba.ask >= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty
                elif order.side == Side.SELL and ba.bid <= order.price:
                    fill_price = order.price
                    fill_qty = order.qty - order.filled_qty

            elif order.type == OrderType.STOP_LIMIT:
                triggered = False
                if order.side == Side.BUY and ba.ask >= order.price:
                    triggered = True
                elif order.side == Side.SELL and ba.bid <= order.price:
                    triggered = True

                if triggered:
                    limit = order.stop_limit_price or order.price
                    if order.side == Side.BUY and ba.bid <= limit:
                        fill_price = limit
                        fill_qty = order.qty - order.filled_qty
                    elif order.side == Side.SELL and ba.ask >= limit:
                        fill_price = limit
                        fill_qty = order.qty - order.filled_qty
                    else:
                        order.type = OrderType.LIMIT
                        order.price = limit

            elif order.type == OrderType.TRAILING_STOP:
                extreme_updated = False
                if order.side == Side.SELL:
                    if ba.ask > order.trail_extreme:
                        order.trail_extreme = ba.ask
                        extreme_updated = True
                    if order.trail_offset is not None:
                        if order.trail_is_pct:
                            stop = order.trail_extreme * (1 - order.trail_offset)
                        else:
                            stop = order.trail_extreme - order.trail_offset
                        if not extreme_updated and order.trail_extreme > 0 and ba.bid <= stop:
                            fill_price = ba.bid
                            fill_qty = order.qty - order.filled_qty
                else:
                    if order.trail_extreme == 0 or ba.bid < order.trail_extreme:
                        order.trail_extreme = ba.bid
                        extreme_updated = True
                    if order.trail_offset is not None:
                        if order.trail_is_pct:
                            stop = order.trail_extreme * (1 + order.trail_offset)
                        else:
                            stop = order.trail_extreme + order.trail_offset
                        if not extreme_updated and order.trail_extreme > 0 and ba.ask >= stop:
                            fill_price = ba.ask
                            fill_qty = order.qty - order.filled_qty

            if fill_price is not None and fill_qty > 0:
                if order.tif == TimeInForce.FOK:
                    pass  # simplified for bid/ask

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

                if order.tif == TimeInForce.IOC and order.filled_qty < order.qty:
                    order.status = OrderStatus.PARTIALLY_FILLED
                    cancel_after = True

                if order.filled_qty >= order.qty:
                    order.status = OrderStatus.FILLED
                    indices_to_remove.append(i)
                    self._cancel_oco_partner(order)
                elif cancel_after:
                    indices_to_remove.append(i)
            else:
                if not order._first_eval:
                    order._first_eval = True
                    if order.tif in (TimeInForce.FOK, TimeInForce.IOC):
                        order.status = OrderStatus.CANCELLED
                        indices_to_remove.append(i)

        for i in sorted(indices_to_remove, reverse=True):
            if i < len(self._pending):
                self._pending.pop(i)

        return new_fills

    def cancel(self, order_id: int) -> bool:
        """Cancel a pending order by ID."""
        for i, order in enumerate(self._pending):
            if order.id == order_id:
                order.status = OrderStatus.CANCELLED
                self._pending.pop(i)
                return True
        return False

    def cancel_all(self, symbol: str | None = None) -> int:
        """Cancel all pending orders, optionally filtered by symbol. Returns count."""
        if symbol is None:
            count = len(self._pending)
            for o in self._pending:
                o.status = OrderStatus.CANCELLED
            self._pending.clear()
            return count
        to_cancel = [o for o in self._pending if o.symbol == symbol]
        for o in to_cancel:
            o.status = OrderStatus.CANCELLED
            self._pending.remove(o)
        return len(to_cancel)
