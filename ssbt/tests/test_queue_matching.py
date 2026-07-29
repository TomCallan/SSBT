"""Unit tests for L3 Queue Priority & Execution Latency Engine."""

import pytest
from ssbt import (
    Order, Side, OrderType, OrderStatus,
    QueuePriorityModel, ExecutionLatencyModel, L3MatchingEngine,
)


def test_queue_priority_model_registration():
    queue_model = QueuePriorityModel(initial_volume_ahead_pct=0.50)
    order = Order(id=101, symbol="BTC", side=Side.BUY, type=OrderType.LIMIT, price=50000.0, qty=1.0, status=OrderStatus.PENDING)

    tracker = queue_model.register_order(order, level_volume=10.0, timestamp=1000)
    assert tracker.volume_ahead == 5.0
    assert tracker.order.id == 101


def test_queue_priority_depletion_and_fill():
    queue_model = QueuePriorityModel(initial_volume_ahead_pct=0.50)
    order = Order(id=102, symbol="BTC", side=Side.BUY, type=OrderType.LIMIT, price=50000.0, qty=1.0, status=OrderStatus.PENDING)

    # Level volume = 10.0 => v_ahead = 5.0
    queue_model.register_order(order, level_volume=10.0, timestamp=1000)

    # 1. Trade print of 3.0 at price 50000.0 => Depletes v_ahead to 2.0 (no fill yet)
    fills = queue_model.process_trade_event(trade_price=50000.0, trade_volume=3.0)
    assert len(fills) == 0
    assert queue_model.active_queues[102].volume_ahead == 2.0

    # 2. Trade print of 4.0 at price 50000.0 => Depletes remaining 2.0 v_ahead and fills 2.0 remaining trade vol => Order FILLED!
    fills = queue_model.process_trade_event(trade_price=50000.0, trade_volume=4.0)
    assert len(fills) == 1
    assert fills[0].qty == 1.0
    assert fills[0].price == 50000.0
    assert order.status == OrderStatus.FILLED


def test_execution_latency_model():
    latency_model = ExecutionLatencyModel(latency_ms=10.0)
    effective_ts = latency_model.apply_latency(1000)
    assert effective_ts == 1010
