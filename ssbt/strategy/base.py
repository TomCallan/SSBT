"""Strategy base class — ABC with precompute pattern.

Strategies override:
  - on_init(engine): called once before event loop. Use for precompute.
  - on_bar(bar, engine): called per bar event.
  - on_bidask(ba, engine): called per bid/ask event.
  - on_finish(engine): called after event loop. Optional.

Submit orders via engine.submit_order(Order(...)).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import polars as pl

from ssbt.core.events import Bar, BidAsk, Order


class Strategy(ABC):
    """Abstract base for backtest strategies.

    The precompute pattern:
      In on_init(), load the full DataFrame from engine.feed and compute
      indicators vectorised (Polars/NumPy). Store signals. Then on_bar()
      just indexes into precomputed arrays — no per-bar Python indicator loops.
    """

    def on_init(self, engine) -> None:
        """Called once before the event loop. Override for precompute."""
        pass

    @abstractmethod
    def on_bar(self, bar: Bar, engine) -> None:
        """Called for each Bar event. Submit orders via engine.submit_order()."""
        ...

    def on_bidask(self, ba: BidAsk, engine) -> None:
        """Called for each BidAsk event. Override if using bid/ask data."""
        pass

    def on_finish(self, engine) -> None:
        """Called after the event loop ends. Override for cleanup/reporting."""
        pass

    # --- Convenience helpers ---

    @staticmethod
    def get_dataframe(engine, symbol: str | None = None) -> pl.DataFrame:
        """Get the full Polars DataFrame for precompute."""
        return engine.feed.get_dataframe(symbol)

    @staticmethod
    def market_order(symbol: str, side, qty: float) -> Order:
        """Create a market order quickly."""
        from ssbt.core.events import OrderType, OrderStatus
        return Order(
            id=0,  # assigned by matching engine
            symbol=symbol,
            side=side,
            type=OrderType.MARKET,
            qty=qty,
            price=None,
            status=OrderStatus.PENDING,
        )

    @staticmethod
    def limit_order(symbol: str, side, qty: float, price: float) -> Order:
        """Create a limit order quickly."""
        from ssbt.core.events import OrderType, OrderStatus
        return Order(
            id=0,
            symbol=symbol,
            side=side,
            type=OrderType.LIMIT,
            qty=qty,
            price=price,
            status=OrderStatus.PENDING,
        )

    @staticmethod
    def stop_order(symbol: str, side, qty: float, price: float) -> Order:
        """Create a stop order quickly."""
        from ssbt.core.events import OrderType, OrderStatus
        return Order(
            id=0,
            symbol=symbol,
            side=side,
            type=OrderType.STOP,
            qty=qty,
            price=price,
            status=OrderStatus.PENDING,
        )
