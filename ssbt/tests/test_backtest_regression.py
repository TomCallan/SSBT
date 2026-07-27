"""Regression tests for the existing backtest engine.

These tests freeze current backtest behaviour. Any change to the engine
that alters these values must be deliberate and reviewed.
"""

from __future__ import annotations

import numpy as np
import pytest

from ssbt.analytics.metrics import compute_metrics
from ssbt.core.engine import Engine
from ssbt.data.feed import ParquetFeed, InMemoryFeed
from ssbt.tests.conftest import _SmaCrossStrategy


class TestBacktestDeterminism:
    """Re-running the same backtest must produce identical results.
    Each run uses a fresh strategy instance.
    """

    def test_equity_curve_deterministic(self, single_symbol_data_path):
        s1 = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)
        feed = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH")
        r1 = Engine(feed, s1, initial_cash=100_000.0).run()
        s2 = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)
        feed2 = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH")
        r2 = Engine(feed2, s2, initial_cash=100_000.0).run()

        assert r1.equity_curve.shape == r2.equity_curve.shape
        assert np.allclose(r1.equity_curve, r2.equity_curve, atol=1e-12)

    def test_fills_deterministic(self, single_symbol_data_path):
        s1 = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)
        feed = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH")
        r1 = Engine(feed, s1, initial_cash=100_000.0).run()
        s2 = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)
        feed2 = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH")
        r2 = Engine(feed2, s2, initial_cash=100_000.0).run()

        assert len(r1.fills) == len(r2.fills)
        for f1, f2 in zip(r1.fills, r2.fills):
            assert f1.timestamp == f2.timestamp
            assert f1.price == pytest.approx(f2.price)

    def test_trades_deterministic(self, single_symbol_data_path):
        s1 = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)
        feed = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH")
        r1 = Engine(feed, s1, initial_cash=100_000.0).run()
        s2 = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)
        feed2 = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH")
        r2 = Engine(feed2, s2, initial_cash=100_000.0).run()

        assert len(r1.trades) == len(r2.trades)
        for t1, t2 in zip(r1.trades, r2.trades):
            assert t1.pnl == pytest.approx(t2.pnl)


class TestBacktestMetrics:
    """Key backtest metrics must match frozen baselines."""

    def test_final_equity(self, backtest_result, baseline_metrics):
        assert backtest_result.final_equity == pytest.approx(baseline_metrics["final_equity"], rel=1e-4)

    def test_total_return(self, backtest_result, baseline_metrics):
        assert backtest_result.total_return == pytest.approx(baseline_metrics["total_return"], rel=1e-4)

    def test_n_events(self, backtest_result):
        assert backtest_result.n_events == 5000

    def test_metric_values(self, backtest_result, baseline_metrics):
        metrics = compute_metrics(backtest_result.equity_curve, backtest_result.trades)
        for key in ["sharpe", "sortino", "calmar", "max_drawdown", "win_rate", "profit_factor"]:
            assert metrics[key] == pytest.approx(baseline_metrics[key], abs=0.005), (
                f"{key}: expected {baseline_metrics[key]:.4f}, got {metrics[key]:.4f}"
            )

    def test_n_trades(self, backtest_result, baseline_metrics):
        assert len(backtest_result.trades) == baseline_metrics["n_trades"]

    def test_avg_trade(self, backtest_result, baseline_metrics):
        metrics = compute_metrics(backtest_result.equity_curve, backtest_result.trades)
        assert metrics["avg_trade"] == pytest.approx(baseline_metrics["avg_trade"], rel=0.01)


class TestFeedConversion:
    """ParquetFeed -> InMemoryFeed must preserve backtest output."""

    def test_inmemory_parity(self, single_symbol_data_path, sma_cross_strategy):
        parquet_feed = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH")
        r_parquet = Engine(parquet_feed, sma_cross_strategy, initial_cash=100_000.0).run()

        df = parquet_feed.get_dataframe()
        inmemory_feed = InMemoryFeed(df, symbol="SYNTH")
        strategy = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)
        r_inmemory = Engine(inmemory_feed, strategy, initial_cash=100_000.0).run()

        assert np.allclose(r_parquet.equity_curve, r_inmemory.equity_curve, atol=1e-10)
        assert len(r_parquet.fills) == len(r_inmemory.fills)
        assert len(r_parquet.trades) == len(r_inmemory.trades)

    def test_inmemory_slice(self, single_symbol_data_path, sma_cross_strategy):
        """Sliced InMemoryFeed produces expected bar count."""
        df = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH").get_dataframe()
        feed = InMemoryFeed(df, symbol="SYNTH", start=100, end=1000)
        assert feed.n_bars == 900


class TestBidAskRegression:
    """Smoke test that bid/ask data path does not crash."""

    def test_bidask_fast_path(self):
        import polars as pl
        import numpy as np
        from ssbt.core.engine import Engine
        from ssbt.data.feed import InMemoryFeed
        from ssbt.strategy.base import Strategy

        ts = np.arange(100) * 60_000_000_000  # 1 min in ns
        df = pl.DataFrame({
            "timestamp": ts,
            "bid": 100.0 + np.random.default_rng(42).normal(0, 0.01, 100).cumsum(),
            "ask": 100.5 + np.random.default_rng(42).normal(0, 0.01, 100).cumsum(),
        })
        feed = InMemoryFeed(df, symbol="TEST")

        class NoopStrategy(Strategy):
            def on_bar(self, bar, engine): ...
            def on_bidask(self, ba, engine): ...

        result = Engine(feed, NoopStrategy(), initial_cash=100_000.0).run()
        assert result.n_events == 100
        assert result.final_equity > 0
