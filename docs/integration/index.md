# Integration & Downstream Systems

---
summary: Integration guide for external GUIs, BacktestAdapter design patterns, downstream artifact contracts, and Context7 LLM optimization.
keywords: integration, gui integration, backtest adapter, context7, llm optimization, artifact contract
domain: integration
difficulty: intermediate
primary_apis: ssbt.service, ssbt.BacktestAdapter, ssbt.analytics.ExecutionStreamPublisher
related_pages: /docs/index.md, /docs/CONTEXT7.md, /docs/use-cases/event-driven-live-streaming.md
---

## 1. GUI Integration Guide
Integrate real-time front-end GUIs using `SocketIPCSink` or `RingBufferIPCSink`.

```python
from ssbt.analytics import ExecutionStreamPublisher, SocketIPCSink

ipc_sink = SocketIPCSink(host="127.0.0.1", port=9099)
publisher = ExecutionStreamPublisher(sinks=[ipc_sink])
engine = Engine(feed=feed, stream_publisher=publisher)
```

## 2. Context7 / LLM Search Optimization

To ensure AI agent retrieval systems (such as Context7 and RAG pipelines) accurately locate and parse SSBT use cases:
- Every doc page includes standardized front-matter YAML (`summary`, `keywords`, `domain`, `difficulty`, `primary_apis`, `related_pages`).
- Machine-readable index provided at `docs/use-cases/index.yaml`.
- High-level Agent cheat sheet maintained at `docs/CONTEXT7.md`.
