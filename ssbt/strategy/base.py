"""Strategy base class — ABC with precompute pattern."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
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
    def get_position_qty(engine, symbol: str) -> float:
        pos = engine.portfolio.positions.get(symbol)
        return pos.qty if pos else 0.0

    @staticmethod
    def is_flat(engine, symbol: str) -> bool:
        pos = engine.portfolio.positions.get(symbol)
        return pos.is_flat() if pos else True

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


def load_strategy_from_source(
    source: str | Path | Strategy | type[Strategy] | Any,
    strategy_name: str | None = None,
    kwargs: dict | None = None,
) -> Strategy:
    """Instantiate a Strategy from a file path, Python code string, Strategy subclass, instance, or function."""
    kwargs = kwargs or {}
    if isinstance(source, Strategy):
        return source
    if isinstance(source, type) and issubclass(source, Strategy):
        return source(**kwargs)
    if callable(source) and not isinstance(source, type):
        from ssbt.quick import FunctionalStrategy
        return FunctionalStrategy(source)

    code_text = ""
    if isinstance(source, Path) or (isinstance(source, str) and (source.endswith(".py") or Path(source).exists())):
        p = Path(source)
        if p.exists() and p.is_file():
            code_text = p.read_text(encoding="utf-8")
        else:
            code_text = str(source)
    else:
        code_text = str(source)

    namespace: dict[str, Any] = {
        "Strategy": Strategy,
        "Side": Side,
        "Order": Order,
        "OrderType": OrderType,
        "OrderStatus": OrderStatus,
        "Bar": Bar,
        "BidAsk": BidAsk,
        "pl": pl,
        "np": np,
    }
    exec(code_text, namespace)

    strat_cls = None
    if strategy_name and strategy_name in namespace:
        val = namespace[strategy_name]
        if isinstance(val, type) and issubclass(val, Strategy) and val is not Strategy:
            strat_cls = val
    if strat_cls is None:
        for v in namespace.values():
            if isinstance(v, type) and issubclass(v, Strategy) and v is not Strategy:
                strat_cls = v
                break

    if strat_cls is None:
        raise ValueError(f"No subclass of Strategy found in provided code source ({source})")

    return strat_cls(**kwargs)

