"""Real-time high-throughput IPC execution stream publisher for SSBT.

Provides an extensible, multi-sink IPC streaming engine for engine bar events,
order submissions, fills, trades, and portfolio updates. Features memory-buffered
file sinks, binary struct sinks, lock-free ring-buffer sinks, socket sinks, queue sinks, and subscriber callbacks.
"""

from __future__ import annotations

import json
import socket
import struct
import threading
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Sequence


class StreamEventType(str, Enum):
    """Standardized IPC event types."""
    BAR = "BAR"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_FILLED = "ORDER_FILLED"
    PARTIAL_FILL = "PARTIAL_FILL"
    TRADE = "TRADE"
    EQUITY_UPDATE = "EQUITY_UPDATE"
    METRICS_UPDATE = "METRICS_UPDATE"
    AUDIT_CHECKPOINT = "AUDIT_CHECKPOINT"


@dataclass
class StreamEvent:
    """IPC stream event payload with monotonic sequence ordering."""
    seq_id: int
    event_type: str
    timestamp: int
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seq_id": self.seq_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "data": self.data,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def to_bytes(self) -> bytes:
        """Binary packed format: uint64 seq_id, uint64 timestamp, uint16 type_len, type_bytes, uint32 json_len, json_bytes."""
        type_bytes = self.event_type.encode("utf-8")
        data_bytes = json.dumps(self.data).encode("utf-8")
        header = struct.pack("<QQHI", self.seq_id, self.timestamp, len(type_bytes), len(data_bytes))
        return header + type_bytes + data_bytes

    @classmethod
    def from_bytes(cls, raw: bytes) -> StreamEvent:
        header_size = struct.calcsize("<QQHI")
        seq_id, timestamp, type_len, json_len = struct.unpack("<QQHI", raw[:header_size])
        offset = header_size
        event_type = raw[offset:offset+type_len].decode("utf-8")
        offset += type_len
        data = json.loads(raw[offset:offset+json_len].decode("utf-8"))
        return cls(seq_id=seq_id, event_type=event_type, timestamp=timestamp, data=data)


class IPCSink(ABC):
    """Abstract interface for IPC stream event sinks."""

    @abstractmethod
    def emit(self, event: StreamEvent) -> None:
        """Emit a single event payload."""
        pass

    def flush(self) -> None:
        """Flush any pending buffered events."""
        pass

    def close(self) -> None:
        """Release underlying system resources."""
        self.flush()


class BufferedFileSink(IPCSink):
    """High-throughput memory-buffered file sink.
    
    Buffers events in memory and writes to disk in chunks to maximize throughput
    and eliminate per-event disk I/O overhead.
    """

    def __init__(self, log_path: Path | str, batch_size: int = 500) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.batch_size = max(1, batch_size)
        self.buffer: list[str] = []
        self._lock = threading.Lock()

        # Initialize/truncate file
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write("")

    def emit(self, event: StreamEvent) -> None:
        json_str = event.to_json()
        with self._lock:
            self.buffer.append(json_str)
            if len(self.buffer) >= self.batch_size:
                self._flush_unlocked()

    def _flush_unlocked(self) -> None:
        if not self.buffer:
            return
        lines = "\n".join(self.buffer) + "\n"
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(lines)
        self.buffer.clear()

    def flush(self) -> None:
        with self._lock:
            self._flush_unlocked()

    def close(self) -> None:
        self.flush()


class RingBufferIPCSink(IPCSink):
    """Ultra-fast lock-free ring-buffer sink for sub-microsecond in-memory event logging."""

    def __init__(self, capacity: int = 100_000) -> None:
        self.capacity = capacity
        self.buffer: deque[StreamEvent] = deque(maxlen=capacity)

    def emit(self, event: StreamEvent) -> None:
        self.buffer.append(event)

    def get_latest(self, n: int = 1) -> list[StreamEvent]:
        return list(self.buffer)[-n:]


class BinaryIPCSink(IPCSink):
    """Binary struct payload file/socket sink for high-efficiency C++/Rust/Go IPC integration."""

    def __init__(self, log_path: Path | str) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = open(self.log_path, "wb")

    def emit(self, event: StreamEvent) -> None:
        payload = event.to_bytes()
        # Pack uint32 payload length prefix
        self._file.write(struct.pack("<I", len(payload)) + payload)

    def flush(self) -> None:
        if not self._file.closed:
            self._file.flush()

    def close(self) -> None:
        if not self._file.closed:
            self.flush()
            self._file.close()


class CallbackIPCSink(IPCSink):
    """Direct callback IPC sink for in-process subscribers."""

    def __init__(self, callback: Callable[[StreamEvent], None]) -> None:
        self.callback = callback

    def emit(self, event: StreamEvent) -> None:
        try:
            self.callback(event)
        except Exception:
            pass


class QueueIPCSink(IPCSink):
    """Thread-safe queue sink for async consumers."""

    def __init__(self, maxsize: int = 10000) -> None:
        self.queue: Queue[StreamEvent] = Queue(maxsize=maxsize)

    def emit(self, event: StreamEvent) -> None:
        try:
            self.queue.put_nowait(event)
        except Exception:
            pass

    def get_event(self, block: bool = True, timeout: float | None = None) -> StreamEvent | None:
        try:
            return self.queue.get(block=block, timeout=timeout)
        except Empty:
            return None


class SocketIPCSink(IPCSink):
    """TCP Socket IPC sink for streaming events to external processes/dashboards."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9999, binary_mode: bool = False) -> None:
        self.host = host
        self.port = port
        self.binary_mode = binary_mode
        self.sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._connect()

    def _connect(self) -> None:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(0.5)
            self.sock.connect((self.host, self.port))
        except Exception:
            self.sock = None

    def emit(self, event: StreamEvent) -> None:
        if not self.sock:
            return
        if self.binary_mode:
            raw = event.to_bytes()
            payload = struct.pack("<I", len(raw)) + raw
        else:
            payload = (event.to_json() + "\n").encode("utf-8")
            
        with self._lock:
            try:
                self.sock.sendall(payload)
            except Exception:
                self.sock = None

    def close(self) -> None:
        with self._lock:
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass
                self.sock = None


class ExecutionStreamPublisher:
    """Publishes real-time engine execution events across multi-sink IPC channels."""

    def __init__(
        self,
        log_path: Path | str | None = None,
        enable_console: bool = False,
        sinks: Sequence[IPCSink] | None = None,
        enabled: bool = True,
        batch_size: int = 500,
    ) -> None:
        self.enabled = enabled
        self.enable_console = enable_console
        self.sinks: list[IPCSink] = list(sinks) if sinks else []
        self._seq_counter = 0

        # Backward compatibility for log_path argument
        if log_path:
            self.sinks.append(BufferedFileSink(log_path=log_path, batch_size=batch_size))

    def add_sink(self, sink: IPCSink) -> None:
        """Attach a new IPC sink to the publisher."""
        self.sinks.append(sink)

    def subscribe(self, callback: Callable[[StreamEvent], None]) -> None:
        """Register a subscriber callback function via CallbackIPCSink."""
        self.add_sink(CallbackIPCSink(callback))

    def publish(self, event_type: str | StreamEventType, timestamp: int, data: dict[str, Any]) -> None:
        """Publish an execution event to all active sinks."""
        if not self.enabled or (not self.sinks and not self.enable_console):
            return

        self._seq_counter += 1
        event_str = event_type.value if isinstance(event_type, StreamEventType) else str(event_type)
        event = StreamEvent(
            seq_id=self._seq_counter,
            event_type=event_str,
            timestamp=timestamp,
            data=data,
        )

        for sink in self.sinks:
            sink.emit(event)

        if self.enable_console:
            print(f"[IPC #{event.seq_id}] {event.event_type} | {event.timestamp} | {event.data}")

    def flush(self) -> None:
        """Flush all pending sinks."""
        for sink in self.sinks:
            sink.flush()

    def close(self) -> None:
        """Close all sinks and release resources."""
        for sink in self.sinks:
            sink.close()
