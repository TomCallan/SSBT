"""Live Real-Time Data Stream Feed for SSBT.

Enables external real-time data sources (WebSockets, REST endpoints, ZeroMQ, gRPC)
to push market ticks, bid/ask quotes, and bar updates directly into SSBT.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from enum import Enum
from queue import Empty, Full, Queue
from typing import Union

from ssbt.core.events import Bar, BidAsk, GenericTickEvent


class QueueOverflowPolicy(str, Enum):
    """Queue overflow policies when high-frequency tick ingestion exceeds queue capacity."""
    BLOCK = "BLOCK"
    DISCARD_OLDEST = "DISCARD_OLDEST"
    RAISE_OVERFLOW = "RAISE_OVERFLOW"


class LiveStreamFeed:
    """Thread-safe feed for real-time streaming market data.
    
    External WebSocket/REST adapters push events via `push_bar`, `push_bidask`,
    `push_tick`, or `push_event`. SSBT's Engine consumes events from the feed iterator in real-time.
    """

    def __init__(
        self,
        symbols: list[str] | str | None = None,
        max_queue_size: int = 100_000,
        timeout: float | None = 1.0,
        overflow_policy: QueueOverflowPolicy | str = QueueOverflowPolicy.DISCARD_OLDEST,
    ) -> None:
        if isinstance(symbols, str):
            self._symbols = [symbols]
        elif symbols:
            self._symbols = list(symbols)
        else:
            self._symbols = ["LIVE"]

        self._queue: Queue[Union[Bar, BidAsk, GenericTickEvent, None]] = Queue(maxsize=max_queue_size)
        self.timeout = timeout
        self.overflow_policy = QueueOverflowPolicy(overflow_policy)
        self._stopped = False
        self._events_received = 0
        self._events_dropped = 0

    @property
    def symbols(self) -> list[str]:
        return self._symbols

    @property
    def events_received(self) -> int:
        return self._events_received

    @property
    def events_dropped(self) -> int:
        return self._events_dropped

    @staticmethod
    def current_nanos() -> int:
        """Utility returning current monotonic time in nanoseconds."""
        return int(time.time_ns())

    def push_bar(
        self,
        timestamp: int | None,
        symbol: str,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float = 0.0,
    ) -> None:
        """Push a real-time OHLCV Bar event."""
        if self._stopped:
            return
        ts = int(timestamp) if timestamp is not None else self.current_nanos()
        bar = Bar(
            timestamp=ts,
            symbol=symbol,
            open=float(open),
            high=float(high),
            low=float(low),
            close=float(close),
            volume=float(volume),
        )
        self.push_event(bar)

    def push_bidask(
        self,
        timestamp: int | None,
        symbol: str,
        bid: float,
        ask: float,
    ) -> None:
        """Push a real-time Bid/Ask quote event."""
        if self._stopped:
            return
        ts = int(timestamp) if timestamp is not None else self.current_nanos()
        ba = BidAsk(
            timestamp=ts,
            symbol=symbol,
            bid=float(bid),
            ask=float(ask),
        )
        self.push_event(ba)

    def push_tick(
        self,
        timestamp: int | None,
        symbol: str,
        price: float,
        bid: float = 0.0,
        ask: float = 0.0,
        volume: float = 1.0,
    ) -> None:
        """Push a real-time raw trade tick or quote."""
        if self._stopped:
            return
        ts = int(timestamp) if timestamp is not None else self.current_nanos()
        event = GenericTickEvent(
            timestamp=ts,
            symbol=symbol,
            price=float(price),
            bid=float(bid) if bid > 0 else float(price),
            ask=float(ask) if ask > 0 else float(price),
            bid_qty=float(volume),
            ask_qty=float(volume),
            volume=float(volume),
            data_source_type="LIVE_TICK",
        )
        self.push_event(event)

    def push_event(self, event: Union[Bar, BidAsk, GenericTickEvent]) -> None:
        """Push any pre-formed market data event object with overflow handling."""
        if self._stopped:
            return

        try:
            self._queue.put(event, block=(self.overflow_policy == QueueOverflowPolicy.BLOCK), timeout=self.timeout)
            self._events_received += 1
        except Full:
            if self.overflow_policy == QueueOverflowPolicy.DISCARD_OLDEST:
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(event)
                    self._events_dropped += 1
                    self._events_received += 1
                except Exception:
                    pass
            elif self.overflow_policy == QueueOverflowPolicy.RAISE_OVERFLOW:
                raise OverflowError("LiveStreamFeed queue overflow — incoming tick frequency exceeds engine throughput capacity.")

    def stop(self) -> None:
        """Signal the feed to stop streaming and unblock waiting iterator."""
        self._stopped = True
        try:
            self._queue.put_nowait(None)  # Sentinel to unblock queue.get()
        except Full:
            pass

    def __iter__(self) -> Iterator[Union[Bar, BidAsk, GenericTickEvent]]:
        """Yield events as they arrive in real-time."""
        while not self._stopped or not self._queue.empty():
            try:
                event = self._queue.get(block=True, timeout=self.timeout)
                if event is None:
                    # Sentinel received -> stop streaming
                    break
                yield event
            except Empty:
                if self._stopped:
                    break
                continue
