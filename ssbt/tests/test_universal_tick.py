"""Unit tests for UniversalTickStream and dynamic forward-filling data engine."""

import pytest
import polars as pl
from ssbt.data.universal_tick import UniversalTickStream, UniversalTickFeed
from ssbt.core.events import GenericTickEvent
from ssbt.core.matching import MatchingEngine
from ssbt.core.events import Order, OrderType, Side, OrderStatus


def test_universal_tick_stream_build():
    bar_df = pl.DataFrame({
        "timestamp": [1000, 5000],
        "symbol": ["TEST"] * 2,
        "open": [100.0, 105.0],
        "high": [101.0, 106.0],
        "low": [99.0, 104.0],
        "close": [100.0, 105.0],
    })

    l2_df = pl.DataFrame({
        "timestamp": [2000],
        "symbol": ["TEST"],
        "bid": [101.0],
        "ask": [101.5],
    })

    ticks = UniversalTickStream.build_stream(data_sources=[bar_df, l2_df], forward_fill=True)
    assert len(ticks) == 3
    assert ticks[0].timestamp == 1000
    assert ticks[1].timestamp == 2000
    assert ticks[2].timestamp == 5000
    assert ticks[1].bid == 101.0
    assert ticks[1].ask == 101.5


def test_universal_tick_matching():
    tick = GenericTickEvent(
        timestamp=1000,
        symbol="TEST",
        price=100.0,
        bid=99.5,
        ask=100.5,
    )

    engine = MatchingEngine()
    order = Order(id=1, symbol="TEST", side=Side.BUY, type=OrderType.MARKET, qty=1.0, status=OrderStatus.PENDING)
    engine.submit(order)

    fills = engine.process_tick(tick)
    assert len(fills) == 1
    assert fills[0].price >= 100.5
