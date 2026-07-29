"""High-Frequency L3 Orderbook Queue Priority & Microstructure Matching Engine."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import numpy as np

from ssbt.core.events import Order, Fill, Side, OrderType, OrderStatus, Bar, BidAsk


@dataclass
class QueueOrderTracker:
    """Tracks queue position of a limit order at a specific price level."""
    order: Order
    price: float
    volume_ahead: float
    submission_timestamp: int
    fill_timestamp: int | None = None
    filled_qty: float = 0.0


class QueuePriorityModel:
    """FIFO Price-Time Queue Priority Model for L3 Limit Orderbooks."""

    def __init__(self, initial_volume_ahead_pct: float = 0.50):
        self.initial_volume_ahead_pct = initial_volume_ahead_pct
        self.active_queues: dict[int, QueueOrderTracker] = {}

    def register_order(self, order: Order, level_volume: float, timestamp: int) -> QueueOrderTracker:
        """Register a new limit order into the queue with estimated volume ahead."""
        v_ahead = level_volume * self.initial_volume_ahead_pct
        tracker = QueueOrderTracker(
            order=order,
            price=order.price,
            volume_ahead=v_ahead,
            submission_timestamp=timestamp,
        )
        self.active_queues[order.id] = tracker
        return tracker

    def process_trade_event(self, trade_price: float, trade_volume: float) -> list[Fill]:
        """Update volume ahead as market trades occur at the price level, generating fills when v_ahead <= 0."""
        fills: list[Fill] = []

        for order_id, tracker in list(self.active_queues.items()):
            order = tracker.order
            if order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
                continue

            # Check if trade matches order side/price
            is_match = False
            if order.side == Side.BUY and trade_price <= order.price:
                is_match = True
            elif order.side == Side.SELL and trade_price >= order.price:
                is_match = True

            if is_match:
                if tracker.volume_ahead > 0:
                    # Deplete volume ahead in queue
                    depletion = min(tracker.volume_ahead, trade_volume)
                    tracker.volume_ahead -= depletion
                    rem_trade_vol = trade_volume - depletion
                else:
                    rem_trade_vol = trade_volume

                # Fill order if queue ahead is cleared
                if tracker.volume_ahead <= 0 and rem_trade_vol > 0:
                    fill_qty = min(order.qty - tracker.filled_qty, rem_trade_vol)
                    if fill_qty > 0:
                        tracker.filled_qty += fill_qty
                        if tracker.filled_qty >= order.qty:
                            order.status = OrderStatus.FILLED
                            del self.active_queues[order_id]
                        else:
                            order.status = OrderStatus.PARTIALLY_FILLED

                        fills.append(Fill(
                            order_id=order.id,
                            symbol=order.symbol,
                            side=order.side,
                            price=order.price,
                            qty=fill_qty,
                            commission=0.0,
                            timestamp=tracker.submission_timestamp,
                        ))
        return fills


class ExecutionLatencyModel:
    """Simulates feed & network order submission latency in milliseconds."""

    def __init__(self, latency_ms: float = 5.0):
        self.latency_ms = latency_ms

    def apply_latency(self, timestamp: int) -> int:
        """Add latency offset to timestamp (ms)."""
        return int(timestamp + self.latency_ms)


class L3MatchingEngine:
    """High-Frequency L3 Orderbook Queue Priority Matching Engine."""

    def __init__(
        self,
        queue_model: QueuePriorityModel | None = None,
        latency_model: ExecutionLatencyModel | None = None,
    ):
        self.queue_model = queue_model or QueuePriorityModel()
        self.latency_model = latency_model or ExecutionLatencyModel()
        self.pending_orders: list[Order] = []

    def submit_order(self, order: Order, level_volume: float, timestamp: int) -> Order:
        """Submit order with latency and queue priority registration."""
        effective_ts = self.latency_model.apply_latency(timestamp)
        order.status = OrderStatus.PENDING
        self.queue_model.register_order(order, level_volume, effective_ts)
        self.pending_orders.append(order)
        return order

    def process_market_event(self, price: float, volume: float) -> list[Fill]:
        """Process incoming market trade prints against L3 active queues."""
        return self.queue_model.process_trade_event(price, volume)
