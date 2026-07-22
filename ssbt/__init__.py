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
from ssbt.core.events import Bar, BidAsk, Order, Fill, Trade, Side, OrderType, OrderStatus
from ssbt.core.matching import MatchingEngine
from ssbt.core.portfolio import Portfolio
from ssbt.data.feed import ParquetFeed
from ssbt.strategy.base import Strategy

__version__ = "0.1.0"

__all__ = [
    "Engine",
    "BacktestResult",
    "ParquetFeed",
    "MatchingEngine",
    "Portfolio",
    "Strategy",
    "Bar",
    "BidAsk",
    "Order",
    "Fill",
    "Trade",
    "Side",
    "OrderType",
    "OrderStatus",
]
