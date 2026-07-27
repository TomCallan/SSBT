"""Strategy base class — ABC with precompute pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod

import polars as pl

from ssbt.core.events import Bar, BidAsk, Order, OrderStatus, OrderType, Side, TimeInForce


class Strategy(ABC):
    """Override on_init() for precompute, on_bar() for per-bar logic. Submit orders via engine."""

    def on_init(self, engine) -> None:
        pass

    @abstractmethod
    def on_bar(self, bar: Bar, engine) -> None:
        ...

    def on_bidask(self, ba: BidAsk, engine) -> None:
        pass

    def on_finish(self, engine) -> None:
        pass

    @staticmethod
    def get_dataframe(engine, symbol: str | None = None) -> pl.DataFrame:
        return engine.feed.get_dataframe(symbol)

    @staticmethod
    def market_order(symbol, side, qty, tif=TimeInForce.GTC, expire_at=None) -> Order:
        return Order(id=0, symbol=symbol, side=side, type=OrderType.MARKET, qty=qty,
                     tif=tif, expire_at=expire_at, status=OrderStatus.PENDING)

    @staticmethod
    def limit_order(symbol, side, qty, price, tif=TimeInForce.GTC, expire_at=None) -> Order:
        return Order(id=0, symbol=symbol, side=side, type=OrderType.LIMIT, qty=qty, price=price,
                     tif=tif, expire_at=expire_at, status=OrderStatus.PENDING)

    @staticmethod
    def stop_order(symbol, side, qty, price, tif=TimeInForce.GTC, expire_at=None) -> Order:
        return Order(id=0, symbol=symbol, side=side, type=OrderType.STOP, qty=qty, price=price,
                     tif=tif, expire_at=expire_at, status=OrderStatus.PENDING)

    @staticmethod
    def stop_limit_order(symbol, side, qty, stop_price, limit_price, tif=TimeInForce.GTC, expire_at=None) -> Order:
        return Order(id=0, symbol=symbol, side=side, type=OrderType.STOP_LIMIT, qty=qty,
                     price=stop_price, stop_limit_price=limit_price, tif=tif, expire_at=expire_at,
                     status=OrderStatus.PENDING)

    @staticmethod
    def trailing_stop_order(symbol, side, qty, trail_offset, is_pct=False, tif=TimeInForce.GTC, expire_at=None) -> Order:
        return Order(id=0, symbol=symbol, side=side, type=OrderType.TRAILING_STOP, qty=qty,
                     trail_offset=trail_offset, trail_is_pct=is_pct, tif=tif, expire_at=expire_at,
                     status=OrderStatus.PENDING)
