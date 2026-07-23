"""Example: SMA crossover strategy on OHLCV data.

Generates synthetic OHLCV data, runs backtest, prints metrics + saves plot.
Run: python -m ssbt.examples.sma_cross
"""

from __future__ import annotations

import numpy as np
import polars as pl

from ssbt.analytics.metrics import compute_metrics, format_metrics
from ssbt.analytics.plots import plot_equity_curve, plot_drawdown
from ssbt.core.engine import Engine
from ssbt.core.events import Bar, Side
from ssbt.data.feed import ParquetFeed
from ssbt.strategy.base import Strategy


def generate_synthetic_ohlcv(
    n_bars: int = 5000,
    start_price: float = 100.0,
    drift: float = 0.0001,
    volatility: float = 0.01,
    seed: int = 42,
) -> pl.DataFrame:
    """Generate synthetic OHLCV data as a Polars DataFrame."""
    rng = np.random.default_rng(seed)

    # Random walk with drift
    returns = rng.normal(drift, volatility, n_bars)
    close = start_price * np.cumprod(1 + returns)

    # Synthesise OHLV from close
    intrabar_range = np.abs(rng.normal(0, volatility, n_bars)) * close
    open_ = np.roll(close, 1)
    open_[0] = start_price
    high = np.maximum(open_, close) + intrabar_range * rng.uniform(0.1, 0.5, n_bars)
    low = np.minimum(open_, close) - intrabar_range * rng.uniform(0.1, 0.5, n_bars)
    volume = rng.lognormal(15, 1, n_bars)

    # Timestamps: daily bars starting 2020-01-01 (ns epoch)
    ts = (np.datetime64("2020-01-01").astype("datetime64[ns]").astype(np.int64)
          + np.arange(n_bars) * 86_400_000_000_000)  # 1 day in ns

    return pl.DataFrame({
        "timestamp": ts,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


class SmaCrossStrategy(Strategy):
    """SMA crossover: buy when fast > slow, sell when fast < slow.

    Precomputes both SMAs on the full DataFrame in on_init().
    on_bar() just indexes into precomputed arrays.
    """

    def __init__(self, fast_period: int = 10, slow_period: int = 30, qty: float = 100.0):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.qty = qty
        self._signals: np.ndarray | None = None
        self._bar_index: int = 0
        self._symbol: str | None = None
        self._position_qty: float = 0.0

    def on_init(self, engine) -> None:
        # Precompute SMAs vectorised
        symbol = engine.feed.symbols[0]
        self._symbol = symbol
        df = self.get_dataframe(engine, symbol)

        close = df["close"].to_numpy()

        # Rolling SMA via Polars (fast, vectorised)
        df = df.with_columns([
            pl.col("close").rolling_mean(window_size=self.fast_period).alias("sma_fast"),
            pl.col("close").rolling_mean(window_size=self.slow_period).alias("sma_slow"),
        ])

        sma_fast = df["sma_fast"].to_numpy()
        sma_slow = df["sma_slow"].to_numpy()

        # Signal: 1 = bullish (fast > slow), -1 = bearish, 0 = no data
        signals = np.zeros(len(close))
        valid = ~(np.isnan(sma_fast) | np.isnan(sma_slow))
        signals[valid] = np.where(sma_fast[valid] > sma_slow[valid], 1.0, -1.0)

        # Detect crossovers (signal change)
        crossovers = np.zeros(len(close), dtype=bool)
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
            # Bullish crossover — go long
            if self._position_qty < 0:
                # Close short first
                engine.submit_order(self.market_order(
                    self._symbol, Side.BUY, abs(self._position_qty)
                ))
                self._position_qty = 0
            engine.submit_order(self.market_order(
                self._symbol, Side.BUY, self.qty
            ))
            self._position_qty += self.qty

        elif signal < 0 and self._position_qty >= 0:
            # Bearish crossover — go short
            if self._position_qty > 0:
                # Close long first
                engine.submit_order(self.market_order(
                    self._symbol, Side.SELL, self._position_qty
                ))
                self._position_qty = 0
            engine.submit_order(self.market_order(
                self._symbol, Side.SELL, self.qty
            ))
            self._position_qty -= self.qty

    def on_finish(self, engine) -> None:
        # Close any open position at last bar
        if self._position_qty > 0:
            engine.submit_order(self.market_order(
                self._symbol, Side.SELL, self._position_qty
            ))
        elif self._position_qty < 0:
            engine.submit_order(self.market_order(
                self._symbol, Side.BUY, abs(self._position_qty)
            ))


def main():
    df = generate_synthetic_ohlcv(n_bars=5000)
    df.write_parquet("synthetic_ohlcv.parquet")
    print(f"Generated {len(df)} bars")

    feed = ParquetFeed("synthetic_ohlcv.parquet", symbol="SYNTH")
    result = Engine(feed, SmaCrossStrategy(10, 30, 100.0), initial_cash=100_000.0).run()

    metrics = compute_metrics(result.equity_curve, result.trades, periods_per_year=252)
    print(format_metrics(metrics))
    print(f"\nFills: {len(result.fills)} | Trades: {len(result.trades)}")

    plot_equity_curve(result.equity_curve, save_path="equity_curve.png")
    plot_drawdown(result.equity_curve, save_path="drawdown.png")
    print("Saved equity_curve.png, drawdown.png")

    if result.trades:
        pl.DataFrame({
            "symbol": [t.symbol for t in result.trades],
            "entry_time": [t.entry_time for t in result.trades],
            "exit_time": [t.exit_time for t in result.trades],
            "entry_price": [t.entry_price for t in result.trades],
            "exit_price": [t.exit_price for t in result.trades],
            "pnl": [t.pnl for t in result.trades],
        }).write_csv("trade_log.csv")


if __name__ == "__main__":
    main()
