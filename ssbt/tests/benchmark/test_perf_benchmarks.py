"""Performance & scale benchmark suite for SSBT."""

import time
import pytest
import numpy as np
import polars as pl
from ssbt import Engine, InMemoryFeed, Strategy, Side, Bar


class FastPassStrategy(Strategy):
    """High-throughput test strategy."""
    def on_bar(self, bar: Bar, engine) -> None:
        if bar.close > bar.open and self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, 1.0))
        elif bar.close < bar.open and not self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, 1.0))


def test_performance_benchmark_100k_bars():
    n_bars = 100_000
    prices = 100.0 + np.cumsum(np.random.normal(0, 0.5, n_bars))
    df = pl.DataFrame({
        "timestamp": np.arange(n_bars, dtype=np.int64) * 1000,
        "symbol": ["BENCH"] * n_bars,
        "open": prices,
        "high": prices + 0.5,
        "low": prices - 0.5,
        "close": prices + 0.1,
        "volume": np.full(n_bars, 1000.0),
    })

    feed = InMemoryFeed(df, symbol="BENCH")
    strategy = FastPassStrategy()
    engine = Engine(feed, strategy, initial_cash=100000.0)

    start_t = time.perf_counter()
    result = engine.run()
    elapsed = time.perf_counter() - start_t

    bars_per_sec = n_bars / elapsed if elapsed > 0 else 0
    print(f"\n[BENCHMARK] Executed {n_bars:,} bars in {elapsed:.4f}s ({bars_per_sec:,.0f} bars/sec)")

    assert bars_per_sec > 100_000  # Minimum 100k bars/sec speed threshold
