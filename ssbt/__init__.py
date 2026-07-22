"""SSBT — Super Simple Backtesting Tool.

Minimal, performant, event-driven backtester.
Vectorised indicator computation via Polars/NumPy, sequential event-driven execution.

Usage:
    from ssbt import ParquetFeed, Engine, Strategy
    from ssbt.core.events import Side

    feed = ParquetFeed("data.parquet", symbol="BTCUSDT")
    strategy = MyStrategy()
    engine = Engine(feed, strategy)
    result = engine.run()
"""

from ssbt.core.engine import Engine, BacktestResult
from ssbt.core.events import (
    Bar, BidAsk, Order, Fill, Trade, OCOOrder,
    Side, OrderType, OrderStatus, TimeInForce,
)
from ssbt.core.matching import MatchingEngine
from ssbt.core.portfolio import Portfolio
from ssbt.data.feed import InMemoryFeed, ParquetFeed
from ssbt.strategy.base import Strategy
from ssbt.analytics.sweep import param_grid, run_sweep, SweepResult
from ssbt.analytics.walkforward import walk_forward, WalkForwardResult
from ssbt.analytics.metrics import compute_metrics, format_metrics

__version__ = "0.2.0"

__all__ = [
    "Engine",
    "BacktestResult",
    "ParquetFeed",
    "InMemoryFeed",
    "MatchingEngine",
    "Portfolio",
    "Strategy",
    "Bar",
    "BidAsk",
    "Order",
    "Fill",
    "Trade",
    "OCOOrder",
    "Side",
    "OrderType",
    "OrderStatus",
    "TimeInForce",
    "param_grid",
    "run_sweep",
    "SweepResult",
    "walk_forward",
    "WalkForwardResult",
    "compute_metrics",
    "format_metrics",
]
