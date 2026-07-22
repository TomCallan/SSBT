"""Strategy base class — ABC with precompute pattern.

Strategies override:
  - on_init(engine): called once before event loop. Use for precompute.
  - on_bar(bar, engine): called per bar event.
  - on_bidask(ba, engine): called per bid/ask event.
  - on_finish(engine): called after event loop. Optional.

Submit orders via engine.submit_order(Order(...)) or convenience helpers below.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import polars as pl

from ssbt.core.events import (
    Bar,
    BidAsk,
    Order,
    OrderStatus,
    OrderType,
    Side,
    TimeInForce,
)


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
    def market_order(
        symbol: str,
        side: Side,
        qty: float,
        tif: TimeInForce = TimeInForce.GTC,
        expire_at: int | None = None,
    ) -> Order:
        """Create a market order."""
        return Order(
            id=0,
            symbol=symbol,
            side=side,
            type=OrderType.MARKET,
            qty=qty,
            price=None,
            tif=tif,
            expire_at=expire_at,
            status=OrderStatus.PENDING,
        )

    @staticmethod
    def limit_order(
        symbol: str,
        side: Side,
        qty: float,
        price: float,
        tif: TimeInForce = TimeInForce.GTC,
        expire_at: int | None = None,
    ) -> Order:
        """Create a limit order."""
        return Order(
            id=0,
            symbol=symbol,
            side=side,
            type=OrderType.LIMIT,
            qty=qty,
            price=price,
            tif=tif,
            expire_at=expire_at,
            status=OrderStatus.PENDING,
        )

    @staticmethod
    def stop_order(
        symbol: str,
        side: Side,
        qty: float,
        price: float,
        tif: TimeInForce = TimeInForce.GTC,
        expire_at: int | None = None,
    ) -> Order:
        """Create a stop market order."""
        return Order(
            id=0,
            symbol=symbol,
            side=side,
            type=OrderType.STOP,
            qty=qty,
            price=price,
            tif=tif,
            expire_at=expire_at,
            status=OrderStatus.PENDING,
        )

    @staticmethod
    def stop_limit_order(
        symbol: str,
        side: Side,
        qty: float,
        stop_price: float,
        limit_price: float,
        tif: TimeInForce = TimeInForce.GTC,
        expire_at: int | None = None,
    ) -> Order:
        """Create a stop-limit order. Triggers a limit order at limit_price when stop_price hit."""
        return Order(
            id=0,
            symbol=symbol,
            side=side,
            type=OrderType.STOP_LIMIT,
            qty=qty,
            price=stop_price,
            stop_limit_price=limit_price,
            tif=tif,
            expire_at=expire_at,
            status=OrderStatus.PENDING,
        )

    @staticmethod
    def trailing_stop_order(
        symbol: str,
        side: Side,
        qty: float,
        trail_offset: float,
        is_pct: bool = False,
        tif: TimeInForce = TimeInForce.GTC,
        expire_at: int | None = None,
    ) -> Order:
        """Create a trailing stop order.

        trail_offset: absolute price offset (is_pct=False) or percentage (is_pct=True, e.g. 0.02 = 2%).
        For SELL: trails the highest price, stop = high - offset.
        For BUY: trails the lowest price, stop = low + offset.
        """
        return Order(
            id=0,
            symbol=symbol,
            side=side,
            type=OrderType.TRAILING_STOP,
            qty=qty,
            price=None,
            trail_offset=trail_offset,
            trail_is_pct=is_pct,
            tif=tif,
            expire_at=expire_at,
            status=OrderStatus.PENDING,
        )

    @staticmethod
    def oco_order(
        order_a: Order,
        order_b: Order,
    ) -> tuple[Order, Order]:
        """Link two orders as OCO. Submit via engine.submit_oco(*strategy.oco_order(a, b))."""
        return order_a, order_b
