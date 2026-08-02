# Event-Driven Live IPC Streaming

---
summary: Streaming execution telemetry, fills, orders, and portfolio equity live into external GUI applications over IPC sinks.
keywords: event driven, live streaming, ipc, socket sink, ring buffer, zero copy, web interface
domain: infrastructure
difficulty: advanced
primary_apis: ssbt.analytics.ExecutionStreamPublisher, ssbt.analytics.SocketIPCSink, ssbt.analytics.RingBufferIPCSink
related_pages: /docs/use-cases/index.md, /docs/reference/streaming_ipc.md, /docs/integration/index.md
---

## 1. Objective
Stream backtest and live simulation event telemetry (`Bar`, `Order`, `Fill`, `Trade`, `Equity`) asynchronously to external front-end GUIs or dashboards using zero-copy binary and socket IPC sinks.

## 2. Inputs
- **Stream Publisher**: `ExecutionStreamPublisher` attached to `Engine`
- **IPC Sink Configuration**: Unix Domain Socket or TCP Socket (`localhost:9099`) or Ring Buffer Sink

## 3. Minimal Code

```python
from ssbt import Engine, InMemoryFeed, Strategy, OrderType, generate_synthetic_bars
from ssbt.analytics import ExecutionStreamPublisher, SocketIPCSink, StreamEventType

# Configure socket IPC sink targeting local GUI port
ipc_sink = SocketIPCSink(host="127.0.0.1", port=9099, retry_count=3)
publisher = ExecutionStreamPublisher(sinks=[ipc_sink])

df = generate_synthetic_bars(num_bars=500, start_price=100.0, volatility=0.01, seed=42)
feed = InMemoryFeed({"BTC-USD": df})

class StreamingStrategy(Strategy):
    def on_bar(self, engine, bar):
        pos = self.get_position_qty(engine, bar.symbol)
        if pos == 0:
            self.buy(engine, bar.symbol, qty=1.0, order_type=OrderType.MARKET)

engine = Engine(feed=feed, stream_publisher=publisher)
result = engine.run(StreamingStrategy())
print(f"Events published over IPC: {publisher.events_published}")
```

## 4. Realistic Settings
- **Buffering Policy**: `QueueOverflowPolicy.DROP_OLDEST` to prevent main loop backpressure blocking.
- **Serialization Format**: High-efficiency struct pack binary format (`StreamEvent.to_bytes()`).

## 5. Expected Artifacts
```
artifacts/live_stream_run/
├── live_telemetry.bin
└── stream_summary.json
```

## 6. Failure Modes
- **Connection Refused**: GUI receiver process not listening on target port; handled gracefully by `SocketIPCSink` fallback buffer.
- **Queue Overflow**: Consumer too slow; managed via non-blocking ring buffer.

## 7. Validation Checks
```python
assert publisher.events_published > 0, "No IPC stream events were published"
assert publisher.failed_deliveries == 0, "IPC socket stream suffered dropped packets"
```

## 8. Production Checklist
- [ ] Launch IPC receiver listener before starting simulation.
- [ ] Confirm port 9099 is unblocked by network firewall.
- [ ] Set `QueueOverflowPolicy` according to telemetry drop sensitivity.
