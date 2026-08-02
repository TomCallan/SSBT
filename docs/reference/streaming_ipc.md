# Streaming & IPC API Reference (`ssbt.analytics`)

---
summary: API reference for real-time execution stream publishers, socket sinks, ring buffer sinks, and binary serialization.
keywords: reference, streaming, ipc, ExecutionStreamPublisher, SocketIPCSink, RingBufferIPCSink
domain: api-reference
difficulty: advanced
primary_apis: ssbt.analytics.ExecutionStreamPublisher, ssbt.analytics.SocketIPCSink, ssbt.analytics.RingBufferIPCSink, ssbt.analytics.StreamEvent
related_pages: /docs/index.md, /docs/reference/index.md, /docs/use-cases/event-driven-live-streaming.md
---

## `ssbt.analytics.ExecutionStreamPublisher`

Event publisher broadcasting simulation events (`Bar`, `Order`, `Fill`, `Equity`) to registered IPC sinks.

```python
class ExecutionStreamPublisher:
    def __init__(self, sinks: List[BaseIPCSink])
```

## `ssbt.analytics.SocketIPCSink`

TCP/Unix domain socket IPC sink.

```python
class SocketIPCSink(BaseIPCSink):
    def __init__(self, host: str = "127.0.0.1", port: int = 9099, retry_count: int = 3)
```

## `ssbt.analytics.RingBufferIPCSink`

High-throughput in-memory circular ring buffer IPC sink.

```python
class RingBufferIPCSink(BaseIPCSink):
    def __init__(self, capacity: int = 10000)
```
