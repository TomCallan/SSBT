"""Unit tests for Orderbook Engine, multi-resolution L2 reconstruction, and worst-case execution ordering."""

import pytest
import polars as pl
from ssbt.data.orderbook import rebuild_orderbook_from_bars, OrderBookEngine, OrderBookFeed, OrderBookQuote
from ssbt.core.matching import MatchingEngine
from ssbt.core.events import Order, OrderType, Side, OrderStatus, Bar


def test_rebuild_orderbook_from_bars():
    df = pl.DataFrame({
        "timestamp": [1000, 2000],
        "symbol": ["GC=F"] * 2,
        "open": [2000.0, 2005.0],
        "high": [2010.0, 2010.0],
        "low": [1990.0, 2000.0],
        "close": [2005.0, 2008.0],
        "volume": [1000.0, 1200.0],
    })

    # Sub-bar splits = 10 (reconstruct 10 sub-ticks per bar)
    quotes = rebuild_orderbook_from_bars(df, sub_bar_splits=10, spread_pct=0.0002, depth_levels=5)
    assert len(quotes) == 20
    assert quotes[0].bid < quotes[0].ask
    assert len(quotes[0].bids) == 5
    assert len(quotes[0].asks) == 5


def test_orderbook_engine_to_dataframe():
    df = pl.DataFrame({
        "timestamp": [1000],
        "symbol": ["GC=F"],
        "close": [2000.0],
        "volume": [1000.0],
    })

    quotes = OrderBookEngine.reconstruct(df, sub_bar_splits=5)
    ob_df = OrderBookEngine.to_dataframe(quotes)
    assert len(ob_df) == 5
    assert "bid" in ob_df.columns
    assert "ask" in ob_df.columns


def test_worst_case_execution_ordering():
    engine = MatchingEngine()
    
    limit_ord = Order(id=1, symbol="TEST", side=Side.SELL, type=OrderType.LIMIT, qty=1.0, price=105.0, status=OrderStatus.PENDING)
    stop_ord = Order(id=2, symbol="TEST", side=Side.SELL, type=OrderType.STOP, qty=1.0, price=95.0, status=OrderStatus.PENDING)
    
    engine.submit(limit_ord)
    engine.submit(stop_ord)

    bar = Bar(timestamp=1000, symbol="TEST", open=100.0, high=106.0, low=94.0, close=100.0, volume=1000.0)
    fills = engine.process_bar(bar)

    assert len(fills) > 0
    # Worst-case: Adverse Stop Loss (id=2) matched FIRST
    assert fills[0].order_id == 2
