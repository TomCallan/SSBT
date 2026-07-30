"""Unit and integration tests for extensible IPC streaming system."""

import json
import socket
import threading
from pathlib import Path
import pytest

from ssbt.analytics.stream import (
    ExecutionStreamPublisher,
    StreamEvent,
    StreamEventType,
    BufferedFileSink,
    CallbackIPCSink,
    QueueIPCSink,
    SocketIPCSink,
)


def test_buffered_file_sink_batching(tmp_path: Path):
    log_file = tmp_path / "ipc_stream.jsonl"
    sink = BufferedFileSink(log_path=log_file, batch_size=3)

    event1 = StreamEvent(seq_id=1, event_type="BAR", timestamp=1000, data={"close": 100.0})
    event2 = StreamEvent(seq_id=2, event_type="ORDER_SUBMITTED", timestamp=1001, data={"qty": 10})
    event3 = StreamEvent(seq_id=3, event_type="ORDER_FILLED", timestamp=1002, data={"price": 100.0})

    sink.emit(event1)
    sink.emit(event2)
    # File should still be empty before batch_size threshold
    with open(log_file, "r") as f:
        assert f.read() == ""

    sink.emit(event3)
    # Threshold reached -> auto flush
    with open(log_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 3
        data1 = json.loads(lines[0])
        assert data1["seq_id"] == 1
        assert data1["event_type"] == "BAR"

    sink.close()


def test_callback_ipc_sink():
    received = []

    def handle_event(event: StreamEvent):
        received.append(event)

    sink = CallbackIPCSink(callback=handle_event)
    event = StreamEvent(seq_id=1, event_type="TRADE", timestamp=2000, data={"pnl": 50.0})
    sink.emit(event)

    assert len(received) == 1
    assert received[0].seq_id == 1
    assert received[0].data["pnl"] == 50.0


def test_queue_ipc_sink():
    sink = QueueIPCSink(maxsize=10)
    event = StreamEvent(seq_id=1, event_type="EQUITY_UPDATE", timestamp=3000, data={"equity": 10500.0})
    sink.emit(event)

    pop_event = sink.get_event(block=False)
    assert pop_event is not None
    assert pop_event.event_type == "EQUITY_UPDATE"
    assert pop_event.data["equity"] == 10500.0


def test_socket_ipc_sink_graceful_fail():
    # Attempting to connect to unopened port should not crash
    sink = SocketIPCSink(host="127.0.0.1", port=59999)
    event = StreamEvent(seq_id=1, event_type="BAR", timestamp=4000, data={})
    sink.emit(event)
    sink.close()


def test_execution_stream_publisher_multi_sink(tmp_path: Path):
    log_file = tmp_path / "multi_ipc.jsonl"
    events_received = []

    file_sink = BufferedFileSink(log_path=log_file, batch_size=10)
    cb_sink = CallbackIPCSink(callback=lambda e: events_received.append(e))
    queue_sink = QueueIPCSink()

    publisher = ExecutionStreamPublisher(sinks=[file_sink, cb_sink, queue_sink])

    publisher.publish(StreamEventType.BAR, timestamp=1000, data={"close": 50.0})
    publisher.publish(StreamEventType.ORDER_SUBMITTED, timestamp=1001, data={"qty": 5})

    assert len(events_received) == 2
    assert events_received[0].seq_id == 1
    assert events_received[1].seq_id == 2
    assert events_received[0].event_type == "BAR"

    q_event = queue_sink.get_event()
    assert q_event.seq_id == 1

    publisher.flush()
    publisher.close()

    with open(log_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2
