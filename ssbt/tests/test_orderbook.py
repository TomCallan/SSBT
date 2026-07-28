"""Unit tests for Orderbook Engine, synthetic L2 reconstruction, and worst-case execution ordering."""

import pytest
import polars as pl
from ssbt.data.orderbook import rebuild_orderbook_from_bars, OrderBookFeed, OrderBookQuote
from ssbt.core.matching import MatchingEngine
from ssbt.core.events import Order, OrderType, Side, OrderStatus, Bar


def test_rebuild_orderbook_from_bars():
    df = pl.DataFrame({
        "timestamp": [1000, 2000],
        "symbol": ["GC=F"] * 2,
        "close": [2000.0, 2005.0],
        "volume": [1000.0, 1200.0],
    })

    quotes = rebuild_orderbook_from_bars(df, spread_pct=0.0002, depth_levels=5)
    assert len(quotes) == 2
    assert quotes[0].bid < quotes[0].ask
    assert len(quotes[0].bids) == 5
    assert len(quotes[0].asks) == 5


def test_worst_case_execution_ordering():
    engine = MatchingEngine()
    
    # Submit Profit Limit (Priority 1) first, then Stop Loss (Priority 0) second
    limit_ord = Order(id=1, symbol="TEST", side=Side.SELL, type=OrderType.LIMIT, qty=1.0, price=105.0, status=OrderStatus.PENDING)
    stop_ord = Order(id=2, symbol="TEST", side=Side.SELL, type=OrderType.STOP, qty=1.0, price=95.0, status=OrderStatus.PENDING)
    
    engine.submit(limit_ord)
    engine.submit(stop_ord)

    # Bar that touches both Stop (low 94.0) and Limit (high 106.0)
    bar = Bar(timestamp=1000, symbol="TEST", open=100.0, high=106.0, low=94.0, close=100.0, volume=1000.0)
    fills = engine.process_bar(bar)

    assert len(fills) > 0
    # Worst-case: Adverse Stop Loss (id=2) matched FIRST
    assert fills[0].order_id == 2
