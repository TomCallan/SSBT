"""Core event types for the SSBT backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class Side(Enum):
    BUY = auto()
    SELL = auto()


class OrderType(Enum):
    MARKET = auto()
    LIMIT = auto()
    STOP = auto()            # Stop market: triggers market order when stop hit
    STOP_LIMIT = auto()      # Stop triggers limit order at stop_limit_price
    STOP_MARKET = auto()     # Alias for STOP (explicit)
    TRAILING_STOP = auto()   # Trailing stop: track price by offset/percentage


class OrderStatus(Enum):
    PENDING = auto()
    FILLED = auto()
    CANCELLED = auto()
    PARTIALLY_FILLED = auto()
    EXPIRED = auto()


class TimeInForce(Enum):
    GTC = auto()   # Good Till Cancelled
    GTD = auto()   # Good Till Date — expires at expire_at timestamp
    IOC = auto()   # Immediate Or Cancel — fill what you can, cancel rest
    FOK = auto()   # Fill Or Kill — fill entirely or cancel immediately
    DAY = auto()   # Good for session — expires at day boundary


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
    price: float | None = None             # limit/stop price
    tif: TimeInForce = TimeInForce.GTC
    expire_at: int | None = None           # for GTD (ns epoch)
    stop_limit_price: float | None = None  # for STOP_LIMIT
    trail_offset: float | None = None      # for TRAILING_STOP (absolute or pct)
    trail_is_pct: bool = False
    oco_pair_id: int | None = None         # link to OCO partner order id
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    created_at: int = 0                    # ns epoch
    # Internal: trail tracking (highest for sell, lowest for buy)
    trail_extreme: float = 0.0
    # Internal: flag for IOC/FOK first evaluation
    _first_eval: bool = False


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


@dataclass(slots=True)
class OCOOrder:
    """One-Cancels-Other: two linked orders. When one fills, the other is cancelled."""
    order_a: Order
    order_b: Order
    pair_id: int = 0
    active: bool = True
