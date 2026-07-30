"""SSBT Quickstart & High-Level Ergonomics API for Human Quants & Fast Prototyping."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Union

import numpy as np
import polars as pl

from ssbt.analytics.metrics import compute_metrics
from ssbt.analytics.terminal import display_backtest_summary
from ssbt.core.engine import BacktestResult, Engine
from ssbt.core.events import Bar
from ssbt.data.feed import InMemoryFeed, ParquetFeed
from ssbt.strategy.base import Strategy


@dataclass
class QuickResult:
    """Rich ergonomic wrapper for backtest execution results."""

    result: BacktestResult
    metrics: dict[str, Any]
    symbol: str = "ASSET"

    @property
    def equity_curve(self) -> np.ndarray:
        return self.result.equity_curve

    @property
    def fills(self) -> list:
        return self.result.fills

    @property
    def trades(self) -> list:
        return self.result.trades

    @property
    def total_return(self) -> float:
        return float(self.metrics.get("total_return", self.result.total_return))

    @property
    def sharpe_ratio(self) -> float:
        val = self.metrics.get("sharpe", self.metrics.get("sharpe_ratio", 0.0))
        return float(val) if val is not None else 0.0


    @property
    def max_drawdown(self) -> float:
        return float(self.metrics.get("max_drawdown", 0.0))

    @property
    def n_events(self) -> int:
        return self.result.n_events

    def to_dict(self) -> dict[str, Any]:
        """Export metrics and performance statistics to dictionary."""
        return {
            "symbol": self.symbol,
            "n_events": self.n_events,
            "n_fills": len(self.fills),
            "n_trades": len(self.trades),
            "metrics": self.metrics,
            "final_equity": self.result.final_equity,
        }

    def to_json(self, indent: int = 2) -> str:
        """Export result summary as clean JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def plot(self, show: bool = True) -> Any:
        """Render equity curve visualization."""
        from ssbt.analytics.plots import plot_equity_curve

        return plot_equity_curve(self.result.equity_curve, title=f"Backtest — {self.symbol}")

    def __repr__(self) -> str:
        ret_pct = self.total_return * 100
        sharpe = self.sharpe_ratio
        mdd_pct = self.max_drawdown * 100
        return (
            f"<QuickResult symbol='{self.symbol}' events={self.n_events} "
            f"return={ret_pct:+.2f}% sharpe={sharpe:.2f} max_dd={mdd_pct:.2f}%>"
        )


class FunctionalStrategy(Strategy):
    """Wraps a simple bar function as a valid SSBT Strategy."""

    def __init__(self, bar_fn: Callable[[Bar, Engine], None]):
        self._bar_fn = bar_fn

    def on_bar(self, bar: Bar, engine: Engine) -> None:
        self._bar_fn(bar, engine)


def strategy(fn_or_cls: Union[Callable, type, None] = None):
    """Decorator to convert a function `fn(bar, engine)` into a Strategy class or instance.

    Usage:
        @ssbt.strategy
        def my_strategy(bar, engine):
            if bar.close > bar.open:
                engine.submit_order(Strategy.market_order(bar.symbol, Side.BUY, 1.0))
    """

    def decorator(fn: Callable) -> type[Strategy]:
        if isinstance(fn, type) and issubclass(fn, Strategy):
            return fn

        class SimpleStrategy(Strategy):
            def on_bar(self, bar: Bar, engine: Engine) -> None:
                fn(bar, engine)

        SimpleStrategy.__name__ = getattr(fn, "__name__", "SimpleStrategy")
        SimpleStrategy.__doc__ = getattr(fn, "__doc__", "")
        return SimpleStrategy

    if fn_or_cls is None:
        return decorator
    if isinstance(fn_or_cls, type) and issubclass(fn_or_cls, Strategy):
        return fn_or_cls
    return decorator(fn_or_cls)


def generate_synthetic_bars(
    n_bars: int = 1000,
    start_price: float = 100.0,
    volatility: float = 0.01,
    drift: float = 0.0001,
    start_time: datetime | None = None,
    time_step: timedelta = timedelta(minutes=1),
    seed: int = 42,
) -> pl.DataFrame:
    """Generate realistic OHLCV bars for instant strategy testing without external files."""
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(drift, volatility, size=n_bars)
    price_paths = start_price * np.exp(np.cumsum(log_returns))

    opens = np.roll(price_paths, 1)
    opens[0] = start_price
    closes = price_paths

    highs = np.maximum(opens, closes) * (1.0 + np.abs(rng.normal(0, volatility * 0.5, size=n_bars)))
    lows = np.minimum(opens, closes) * (1.0 - np.abs(rng.normal(0, volatility * 0.5, size=n_bars)))
    volumes = rng.lognormal(mean=5.0, sigma=0.5, size=n_bars)

    base_time = start_time or datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc)
    base_ms = int(base_time.timestamp() * 1000)
    step_ms = int(time_step.total_seconds() * 1000)
    timestamps = [base_ms + i * step_ms for i in range(n_bars)]

    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def quick_backtest(
    strategy_input: Strategy | type[Strategy] | Callable[[Bar, Engine], None],
    data: pl.DataFrame | Any | str | Path | InMemoryFeed | ParquetFeed,
    symbol: str = "BTC-USD",
    initial_cash: float = 100_000.0,
    plot: bool = False,
    verbose: bool = False,
) -> QuickResult:
    """One-line ergonomic backtesting helper.

    Args:
        strategy_input: Strategy instance, Strategy class, or bar-handling function.
        data: Polars/Pandas DataFrame, file path (CSV/Parquet), or DataFeed.
        symbol: Symbol identifier for the feed.
        initial_cash: Starting portfolio capital.
        plot: If True, renders equity curve plot.
        verbose: If True, displays CLI terminal summary table.
    """
    from ssbt.strategy.base import load_strategy_from_source
    from ssbt.data.feed import normalise_market_data

    # 1. Prepare strategy
    strat = load_strategy_from_source(strategy_input)

    # 2. Prepare feed
    if isinstance(data, (InMemoryFeed, ParquetFeed)):
        feed = data
    else:
        df = normalise_market_data(data, symbol=symbol)
        feed = InMemoryFeed(df, symbol=symbol)

    # 3. Run engine
    engine = Engine(feed=feed, strategy=strat, initial_cash=initial_cash)
    res = engine.run()

    # 4. Metrics & Summary
    metrics = compute_metrics(res.equity_curve, res.trades)
    quick_res = QuickResult(result=res, metrics=metrics, symbol=symbol)

    if verbose:
        display_backtest_summary(metrics, initial_cash=initial_cash, symbol=symbol)

    if plot:
        quick_res.plot()

    return quick_res
