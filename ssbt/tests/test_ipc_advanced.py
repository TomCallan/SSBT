"""Unit tests for BinaryIPCSink, RingBufferIPCSink, and struct packing."""

from pathlib import Path
import pytest

from ssbt.analytics.stream import (
    StreamEvent,
    BinaryIPCSink,
    RingBufferIPCSink,
)


def test_stream_event_binary_serialization():
    event = StreamEvent(seq_id=42, event_type="ORDER_FILLED", timestamp=1600000000000, data={"qty": 10.0, "price": 100.5})
    raw_bytes = event.to_bytes()
    assert isinstance(raw_bytes, bytes)

    deserialized = StreamEvent.from_bytes(raw_bytes)
    assert deserialized.seq_id == 42
    assert deserialized.event_type == "ORDER_FILLED"
    assert deserialized.timestamp == 1600000000000
    assert deserialized.data["qty"] == 10.0
    assert deserialized.data["price"] == 100.5


def test_ring_buffer_ipc_sink():
    sink = RingBufferIPCSink(capacity=3)
    e1 = StreamEvent(seq_id=1, event_type="BAR", timestamp=100, data={})
    e2 = StreamEvent(seq_id=2, event_type="BAR", timestamp=101, data={})
    e3 = StreamEvent(seq_id=3, event_type="BAR", timestamp=102, data={})
    e4 = StreamEvent(seq_id=4, event_type="BAR", timestamp=103, data={})

    sink.emit(e1)
    sink.emit(e2)
    sink.emit(e3)
    sink.emit(e4)

    latest = sink.get_latest(n=2)
    assert len(latest) == 2
    assert latest[0].seq_id == 3
    assert latest[1].seq_id == 4


def test_binary_ipc_sink(tmp_path: Path):
    bin_path = tmp_path / "stream.bin"
    sink = BinaryIPCSink(log_path=bin_path)

    e1 = StreamEvent(seq_id=10, event_type="TRADE", timestamp=5000, data={"pnl": 12.5})
    sink.emit(e1)
    sink.close()

    assert bin_path.exists()
    assert bin_path.stat().st_size > 0
