"""Core event types for the SSBT backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class Side(Enum):
    BUY = auto()
    SELL = auto()


class OrderType(Enum):
    MARKET = auto()
    LIMIT = auto()
    STOP = auto()


class OrderStatus(Enum):
    PENDING = auto()
    FILLED = auto()
    CANCELLED = auto()
    PARTIALLY_FILLED = auto()


@dataclass(slots=True)
class Bar:
    timestamp: int  # ns epoch
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class BidAsk:
    timestamp: int  # ns epoch
    symbol: str
    bid: float
    ask: float


@dataclass(slots=True)
class Order:
    id: int
    symbol: str
    side: Side
    type: OrderType
    qty: float
    price: float | None = None  # None for market orders
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    created_at: int = 0  # ns epoch


@dataclass(slots=True)
class Fill:
    timestamp: int  # ns epoch
    order_id: int
    symbol: str
    side: Side
    qty: float
    price: float
    commission: float


@dataclass(slots=True)
class Trade:
    """Round-trip trade: entry fill to exit fill."""
    symbol: str
    entry_time: int
    exit_time: int
    entry_price: float
    exit_price: float
    qty: float
    side: Side
    pnl: float
    commission: float
