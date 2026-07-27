"""Smoke tests for multi-symbol backtesting path."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from ssbt.core.events import Bar, Side
from ssbt.core.multi_engine import MultiSymbolEngine
from ssbt.data.feed import InMemoryFeed
from ssbt.portfolio.allocation import equal_weight
from ssbt.strategy.base import Strategy


class _MultiSymbolStrategy(Strategy):
    """Simple SMA-based strategy for multi-symbol smoke tests."""

    def __init__(self, sma_period: int = 20):
        self.sma_period = sma_period
        self._smas: dict[str, np.ndarray] = {}
        self._counts: dict[str, int] = {}

    def on_init(self, engine):
        for sym in engine.symbols:
            df = engine.get_dataframe(sym)
            result = df.with_columns(
                pl.col("close").rolling_mean(window_size=self.sma_period).alias("sma")
            )
            self._smas[sym] = result["sma"].to_numpy()
            self._counts[sym] = 0

    def on_bar(self, bar: Bar, engine):
        idx = self._counts.get(bar.symbol, 0)
        self._counts[bar.symbol] = idx + 1
        sma = self._smas.get(bar.symbol)
        if sma is None or idx >= len(sma) or np.isnan(sma[idx]):
            return
        pos = engine.portfolio.positions.get(bar.symbol)
        if bar.close > sma[idx] and (pos is None or pos.qty == 0):
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, 1.0))
        elif bar.close <= sma[idx] and pos and pos.qty > 0:
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, pos.qty))


def _make_multi_feed(n_bars: int = 500) -> dict[str, InMemoryFeed]:
    """Create a 2-symbol InMemoryFeed dict for testing."""
    rng = np.random.default_rng(42)
    ts = (np.datetime64("2023-01-01").astype("datetime64[ns]").astype(np.int64)
          + np.arange(n_bars) * 86_400_000_000_000)

    feeds = {}
    for name, start, vol in [("AAA", 100, 0.015), ("BBB", 50, 0.02)]:
        close = start * np.cumprod(1 + rng.normal(0.0002, vol, n_bars))
        df = pl.DataFrame({
            "timestamp": ts,
            "open": np.roll(close, 1),
            "high": np.maximum(np.roll(close, 1), close) * 1.01,
            "low": np.minimum(np.roll(close, 1), close) * 0.99,
            "close": close,
            "volume": rng.lognormal(15, 1, n_bars),
        })
        feeds[name] = InMemoryFeed(df, name)
    return feeds


class TestMultiSymbolEngine:
    """Smoke tests for the multi-symbol backtest path."""

    def test_multi_symbol_runs(self):
        feeds = _make_multi_feed(500)
        strategy = _MultiSymbolStrategy(20)
        engine = MultiSymbolEngine(
            feeds=feeds,
            strategy=strategy,
            allocation_fn=equal_weight,
            initial_cash=100_000.0,
            rebalance_freq=5,
        )
        result = engine.run()
        assert result.n_events > 0
        assert result.final_equity > 0
        assert len(engine.symbols) == 2

    def test_multi_symbol_deterministic(self):
        feeds = _make_multi_feed(500)
        r1 = MultiSymbolEngine(
            feeds=feeds,
            strategy=_MultiSymbolStrategy(20),
            allocation_fn=equal_weight,
            initial_cash=100_000.0,
        ).run()
        feeds2 = _make_multi_feed(500)
        r2 = MultiSymbolEngine(
            feeds=feeds2,
            strategy=_MultiSymbolStrategy(20),
            allocation_fn=equal_weight,
            initial_cash=100_000.0,
        ).run()
        assert np.allclose(r1.equity_curve, r2.equity_curve, atol=1e-10)

    def test_multi_symbol_trades_recorded(self):
        feeds = _make_multi_feed(500)
        result = MultiSymbolEngine(
            feeds=feeds,
            strategy=_MultiSymbolStrategy(20),
            allocation_fn=equal_weight,
            initial_cash=100_000.0,
            rebalance_freq=10,
        ).run()
        assert len(result.trades) > 0
        assert len(result.fills) > 0

    def test_custom_allocation_fn(self):
        feeds = _make_multi_feed(500)
        strategy = _MultiSymbolStrategy(20)

        def all_in_first(bars, timestamp):
            return {s: 1.0 if s == "AAA" else 0.0 for s in bars}

        result = MultiSymbolEngine(
            feeds=feeds,
            strategy=strategy,
            allocation_fn=all_in_first,
            initial_cash=100_000.0,
            rebalance_freq=1,
        ).run()
        assert result.final_equity > 0
