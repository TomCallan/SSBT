"""Shared test fixtures for SSBT regression tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from ssbt.core.engine import Engine
from ssbt.core.events import Bar, Side
from ssbt.data.feed import ParquetFeed, InMemoryFeed
from ssbt.strategy.base import Strategy

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
TESTS_DIR = Path(__file__).resolve().parent
FIXTURE_DATA_DIR = TESTS_DIR / "data"
FIXTURE_SINGLE = FIXTURE_DATA_DIR / "synthetic_ohlcv.parquet"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _SmaCrossStrategy(Strategy):
    """Minimal SMA crossover — mirrors ssbt.examples.sma_cross.SmaCrossStrategy."""

    def __init__(self, fast_period: int = 10, slow_period: int = 30, qty: float = 100.0):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.qty = qty
        self._signals: np.ndarray | None = None
        self._bar_index: int = 0
        self._symbol: str | None = None
        self._position_qty: float = 0.0

    def on_init(self, engine) -> None:
        symbol = engine.feed.symbols[0]
        self._symbol = symbol
        df = self.get_dataframe(engine, symbol)

        df = df.with_columns([
            pl.col("close").rolling_mean(window_size=self.fast_period).alias("sma_fast"),
            pl.col("close").rolling_mean(window_size=self.slow_period).alias("sma_slow"),
        ])

        sma_fast = df["sma_fast"].to_numpy()
        sma_slow = df["sma_slow"].to_numpy()

        signals = np.zeros(len(df))
        valid = ~(np.isnan(sma_fast) | np.isnan(sma_slow))
        signals[valid] = np.where(sma_fast[valid] > sma_slow[valid], 1.0, -1.0)

        crossovers = np.zeros(len(df), dtype=bool)
        crossovers[1:] = signals[1:] != signals[:-1]

        self._signals = signals
        self._crossovers = crossovers
        self._bar_index = 0

    def on_bar(self, bar: Bar, engine) -> None:
        idx = self._bar_index
        self._bar_index += 1
        if idx == 0 or not self._crossovers[idx]:
            return
        signal = self._signals[idx]

        if signal > 0 and self._position_qty <= 0:
            if self._position_qty < 0:
                engine.submit_order(self.market_order(self._symbol, Side.BUY, abs(self._position_qty)))
                self._position_qty = 0
            engine.submit_order(self.market_order(self._symbol, Side.BUY, self.qty))
            self._position_qty += self.qty
        elif signal < 0 and self._position_qty >= 0:
            if self._position_qty > 0:
                engine.submit_order(self.market_order(self._symbol, Side.SELL, self._position_qty))
                self._position_qty = 0
            engine.submit_order(self.market_order(self._symbol, Side.SELL, self.qty))
            self._position_qty -= self.qty

    def on_finish(self, engine) -> None:
        if self._position_qty > 0:
            engine.submit_order(self.market_order(self._symbol, Side.SELL, self._position_qty))
        elif self._position_qty < 0:
            engine.submit_order(self.market_order(self._symbol, Side.BUY, abs(self._position_qty)))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def single_symbol_data_path() -> Path:
    """Path to synthetic OHLCV parquet fixture."""
    if not FIXTURE_SINGLE.exists():
        # Auto-generate if missing (e.g. CI checkout without data files)
        from tests.fixtures.generate_fixtures import generate_synthetic_ohlcv  # noqa: PLC0415
        FIXTURE_SINGLE.parent.mkdir(parents=True, exist_ok=True)
        generate_synthetic_ohlcv().write_parquet(FIXTURE_SINGLE)
    return FIXTURE_SINGLE


@pytest.fixture(scope="function")
def sma_cross_strategy():
    """Fresh SmaCross instance per test function."""
    return _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)


@pytest.fixture(scope="session")
def backtest_result(single_symbol_data_path):
    """Run the SmaCross backtest once per session and cache the result.
    Uses its own private strategy instance — not shared with test-level fixtures."""
    feed = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH")
    strategy = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)
    engine = Engine(feed, strategy, initial_cash=100_000.0)
    return engine.run()


# ---------------------------------------------------------------------------
# Baseline metrics (frozen from first run) — update only when intentional
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def baseline_metrics():
    """Known-good metrics for SmaCross(10,30) on synthetic_ohlcv(5000 bars, seed=42).

    Frozen on 2026-07-27. Update only when fixture data or engine behavior
    changes deliberately.
    """
    return {
        "final_equity": 97811.4244,
        "total_return": -0.0218858,
        "sharpe": -0.0976,
        "sortino": -0.0963,
        "calmar": -0.0179,
        "max_drawdown": -0.0623,
        "n_trades": 193,
        "win_rate": 0.3212,
        "profit_factor": 0.9069,
        "avg_trade": -11.5929,
    }
