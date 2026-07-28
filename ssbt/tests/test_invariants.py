"""Property-based accounting & execution invariant tests for SSBT."""

import pytest
import polars as pl
import numpy as np
from ssbt import (
    Engine,
    Portfolio,
    InMemoryFeed,
    Strategy,
    Side,
    Order,
    OrderStatus,
    Bar,
)
from ssbt.data.point_in_time import align_multi_timeframe, validate_point_in_time_join, CausalityViolationError


class InvariantCheckStrategy(Strategy):
    """Strategy that records and verifies invariants on every bar."""
    def __init__(self):
        super().__init__()
        self.invariants_passed = True
        self.bars_processed = 0

    def on_bar(self, bar: Bar, engine) -> None:
        self.bars_processed += 1
        port = engine.portfolio

        # Invariant 1: Position qty == 0 when is_flat() is True
        is_flat_val = self.is_flat(engine, bar.symbol)
        qty_val = self.get_position_qty(engine, bar.symbol)
        if is_flat_val and qty_val != 0.0:
            self.invariants_passed = False

        # Submit buy order on bar 2
        if self.bars_processed == 2:
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, 10.0))

        # Close position on bar 5
        if self.bars_processed == 5:
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, 10.0))


def test_accounting_invariants():
    df = pl.DataFrame({
        "timestamp": [1000, 2000, 3000, 4000, 5000, 6000],
        "symbol": ["TEST"] * 6,
        "open": [100.0, 101.0, 102.0, 105.0, 104.0, 103.0],
        "high": [101.0, 102.0, 106.0, 106.0, 105.0, 104.0],
        "low": [99.0, 100.0, 101.0, 103.0, 103.0, 102.0],
        "close": [100.5, 101.5, 105.0, 104.0, 104.5, 103.5],
        "volume": [100.0] * 6,
    })

    feed = InMemoryFeed(df, symbol="TEST")
    strat = InvariantCheckStrategy()
    engine = Engine(feed, strat, initial_cash=10000.0)
    result = engine.run()

    # Invariant 1 check
    assert strat.invariants_passed is True

    # Invariant 2: Fills causality (fill timestamp >= 1000)
    for fill in engine.matching.fills:
        assert fill.timestamp >= 1000
        assert fill.price > 0.0
        assert fill.qty > 0.0


def test_point_in_time_alignment():
    lower_df = pl.DataFrame({
        "timestamp": [1000, 2000, 3000, 4000],
        "symbol": ["TEST"] * 4,
        "close": [100.0, 101.0, 102.0, 103.0],
    })

    higher_df = pl.DataFrame({
        "timestamp": [2000, 4000],
        "symbol": ["TEST"] * 2,
        "indicator": [50.0, 60.0],
    })

    joined = align_multi_timeframe(lower_df, higher_df)
    assert "htf_indicator" in joined.columns
    # Bar at timestamp 2000 should see null/prior indicator, NOT same-bar close 50.0
    val_at_2000 = joined.filter(pl.col("timestamp") == 2000)["htf_indicator"][0]
    assert val_at_2000 is None or np.isnan(val_at_2000)
