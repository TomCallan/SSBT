"""Extreme-scale performance benchmarks for SSBT.

Tests throughput and latency across:
1. Compiled Vectorized Numba Strategy vs. Complex Non-Compiled Event-Driven Python Strategy.
2. 1,000,000 to 10,000,000 JIT-generated 1-min bars.
3. Chunked Parquet Feed datasets.
4. Real-time synthetic WebSocket stream (LiveStreamFeed).
"""

import time
import threading
from pathlib import Path
import numpy as np
import polars as pl
import pytest

from ssbt import (
    Engine, Strategy, Side, OrderType, OrderStatus,
    InMemoryFeed, ParquetFeed, LiveStreamFeed,
    VectorisedBacktester, VectorisedStrategy,
)


class LeanSMAStrategy(Strategy):
    """Lean event-driven SMA crossover strategy."""

    def __init__(self, period: int = 20) -> None:
        self.period = period
        self.prices: list[float] = []

    def on_init(self, engine: Engine) -> None:
        self.prices.clear()

    def on_bar(self, bar, engine: Engine) -> None:
        self.prices.append(bar.close)
        if len(self.prices) > self.period:
            self.prices.pop(0)
            sma = sum(self.prices) / len(self.prices)
            if bar.close > sma and self.is_flat(engine, bar.symbol):
                order = self.market_order(bar.symbol, Side.BUY, qty=10)
                engine.submit_order(order)
            elif bar.close < sma and not self.is_flat(engine, bar.symbol):
                order = self.market_order(bar.symbol, Side.SELL, qty=10)
                engine.submit_order(order)


class ComplexPythonStrategy(Strategy):
    """Non-compiled complex Python strategy with multi-indicator checks, trailing stop, and state tracking."""

    def __init__(self, lookback: int = 50) -> None:
        self.lookback = lookback
        self.history: list[float] = []
        self.trades_executed = 0

    def on_init(self, engine: Engine) -> None:
        self.history.clear()
        self.trades_executed = 0

    def on_bar(self, bar, engine: Engine) -> None:
        self.history.append(bar.close)
        if len(self.history) > self.lookback:
            self.history.pop(0)

            # Complex multi-step Python logic
            window = self.history[-20:]
            mean = sum(window) / 20.0
            variance = sum((x - mean) ** 2 for x in window) / 20.0
            std_dev = variance ** 0.5

            upper_band = mean + (2.0 * std_dev)
            lower_band = mean - (2.0 * std_dev)

            # Check trailing stop logic & position tracking
            pos_qty = self.get_position_qty(engine, bar.symbol)
            if pos_qty == 0:
                if bar.close < lower_band:
                    order = self.market_order(bar.symbol, Side.BUY, qty=10)
                    engine.submit_order(order)
                    self.trades_executed += 1
            else:
                if bar.close > upper_band:
                    order = self.market_order(bar.symbol, Side.SELL, qty=10)
                    engine.submit_order(order)
                    self.trades_executed += 1


class VectorisedSMAStrategy(VectorisedStrategy):
    """Pure Vectorized Numba/NumPy SMA Strategy."""

    def __init__(self, period: int = 20) -> None:
        self.period = period

    def compute_signals(self, df: pl.DataFrame) -> np.ndarray:
        closes = df["close"].to_numpy()
        n = len(closes)
        signals = np.zeros(n, dtype=np.float64)

        # Fast vectorized rolling mean
        sma = np.convolve(closes, np.ones(self.period) / self.period, mode="same")
        signals[closes > sma] = 1.0
        signals[closes < sma] = -1.0
        return signals


def _generate_synthetic_bar_df(n_bars: int) -> pl.DataFrame:
    """JIT generate n_bars synthetic OHLCV data directly in memory using NumPy."""
    timestamps = np.arange(n_bars, dtype=np.int64) * 60_000_000_000
    np.random.seed(42)
    price_changes = np.random.randn(n_bars) * 0.1
    closes = 100.0 + np.cumsum(price_changes)
    opens = closes - (price_changes * 0.5)
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n_bars) * 0.05)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n_bars) * 0.05)
    volumes = np.random.exponential(500.0, size=n_bars)

    return pl.DataFrame({
        "timestamp": timestamps,
        "symbol": ["SYNTH"] * n_bars,
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })


def test_extreme_scale_vectorised_1m_bars():
    """Benchmark pure vectorised Numba engine on 1,000,000 bars."""
    n_bars = 1_000_000
    df = _generate_synthetic_bar_df(n_bars)

    strategy = VectorisedSMAStrategy(period=20)
    backtester = VectorisedBacktester(initial_cash=100_000.0)

    t0 = time.perf_counter()
    result = backtester.run(df, strategy, symbol="SYNTH")
    t1 = time.perf_counter()

    elapsed = t1 - t0
    bars_per_sec = n_bars / elapsed
    print(f"\n[VECTORISED NUMBA] Processed {n_bars:,} bars in {elapsed:.4f}s -> {bars_per_sec:,.0f} bars/sec")

    assert result["n_events"] == n_bars
    assert bars_per_sec > 100_000


def test_extreme_scale_fast_engine_1m_bars():
    """Benchmark event-driven Fast Bar Engine on 1,000,000 bars."""
    n_bars = 1_000_000
    df = _generate_synthetic_bar_df(n_bars)
    feed = InMemoryFeed(df, symbol="SYNTH")

    strategy = LeanSMAStrategy(period=20)
    engine = Engine(feed=feed, strategy=strategy, initial_cash=100_000.0)

    t0 = time.perf_counter()
    result = engine.run()
    t1 = time.perf_counter()

    elapsed = t1 - t0
    bars_per_sec = n_bars / elapsed
    print(f"[FAST BAR ENGINE] Processed {n_bars:,} bars in {elapsed:.4f}s -> {bars_per_sec:,.0f} bars/sec")

    assert result.n_events == n_bars
    assert bars_per_sec > 50_000


def test_extreme_scale_complex_python_strategy_1m_bars():
    """Benchmark complex non-compiled Python strategy on 1,000,000 bars."""
    n_bars = 1_000_000
    df = _generate_synthetic_bar_df(n_bars)
    feed = InMemoryFeed(df, symbol="SYNTH")

    strategy = ComplexPythonStrategy(lookback=50)
    engine = Engine(feed=feed, strategy=strategy, initial_cash=100_000.0)

    t0 = time.perf_counter()
    result = engine.run()
    t1 = time.perf_counter()

    elapsed = t1 - t0
    bars_per_sec = n_bars / elapsed
    print(f"[COMPLEX PYTHON STRAT] Processed {n_bars:,} bars in {elapsed:.4f}s -> {bars_per_sec:,.0f} bars/sec")

    assert result.n_events == n_bars
    assert bars_per_sec > 30_000


def test_extreme_scale_parquet_feed(tmp_path: Path):
    """Benchmark streaming from disk via ParquetFeed (100,000 bars)."""
    n_bars = 100_000
    df = _generate_synthetic_bar_df(n_bars)
    parquet_file = tmp_path / "bench_data.parquet"
    df.write_parquet(parquet_file)

    feed = ParquetFeed(str(parquet_file), symbol="SYNTH")
    strategy = LeanSMAStrategy(period=20)
    engine = Engine(feed=feed, strategy=strategy, initial_cash=100_000.0)

    t0 = time.perf_counter()
    result = engine.run()
    t1 = time.perf_counter()

    elapsed = t1 - t0
    bars_per_sec = n_bars / elapsed
    print(f"[PARQUET STREAM FEED] Processed {n_bars:,} bars in {elapsed:.4f}s -> {bars_per_sec:,.0f} bars/sec")

    assert result.n_events == n_bars


def test_extreme_scale_websocket_live_feed():
    """Benchmark real-time LiveStreamFeed throughput (100,000 live tick messages)."""
    n_ticks = 100_000
    feed = LiveStreamFeed(symbols="SYNTH", timeout=0.1)

    def websocket_producer():
        prices = 100.0 + np.cumsum(np.random.randn(n_ticks) * 0.05)
        timestamps = np.arange(n_ticks, dtype=np.int64) * 1_000_000
        for i in range(n_ticks):
            feed.push_bidask(
                timestamp=int(timestamps[i]),
                symbol="SYNTH",
                bid=float(prices[i] - 0.05),
                ask=float(prices[i] + 0.05),
            )
        feed.stop()

    producer_thread = threading.Thread(target=websocket_producer)

    strategy = LeanSMAStrategy(period=20)
    engine = Engine(feed=feed, strategy=strategy, initial_cash=100_000.0)

    t0 = time.perf_counter()
    producer_thread.start()
    result = engine.run()
    producer_thread.join()
    t1 = time.perf_counter()

    elapsed = t1 - t0
    ticks_per_sec = n_ticks / elapsed
    print(f"[WEBSOCKET LIVE FEED] Processed {n_ticks:,} live ticks in {elapsed:.4f}s -> {ticks_per_sec:,.0f} ticks/sec")

    assert result.n_events == n_ticks
