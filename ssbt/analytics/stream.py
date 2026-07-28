"""Real-time execution stream publisher for SSBT.

Streams engine bar events, order submissions, fills, trades, and equity updates
in real-time to JSON-lines files or subscriber callbacks for integration with GUIs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Any


@dataclass
class StreamEvent:
    event_type: str  # "BAR", "ORDER", "FILL", "TRADE", "EQUITY"
    timestamp: int
    data: dict[str, Any]


class ExecutionStreamPublisher:
    """Publishes real-time engine execution events to files, sockets, or subscribers."""

    def __init__(self, log_path: Path | str | None = None, enable_console: bool = False) -> None:
        self.log_path = Path(log_path) if log_path else None
        self.enable_console = enable_console
        self.subscribers: list[Callable[[StreamEvent], None]] = []

        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            # Truncate / initialize log file
            with open(self.log_path, "w") as f:
                f.write("")

    def subscribe(self, callback: Callable[[StreamEvent], None]) -> None:
        """Register a subscriber callback function (e.g. for GUI/WebSocket handler)."""
        self.subscribers.append(callback)

    def publish(self, event_type: str, timestamp: int, data: dict[str, Any]) -> None:
        """Publish an execution event to all listeners and file stream."""
        event = StreamEvent(event_type=event_type, timestamp=timestamp, data=data)
        
        # 1. Notify subscribers
        for sub in self.subscribers:
            try:
                sub(event)
            except Exception as e:
                pass

        # 2. Append to JSONL stream file
        if self.log_path:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(asdict(event)) + "\n")

        # 3. Optional console log
        if self.enable_console:
            print(f"[STREAM] {event.event_type} | {event.timestamp} | {event.data}")
