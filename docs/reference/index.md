# SSBT API Reference Index

---
summary: API reference overview split by stable SSBT domains.
keywords: api reference, contract docs, core, feeds, execution, microstructure, risk, overfitting, audit, streaming, cli
domain: api-reference
difficulty: intermediate
primary_apis: ssbt.Engine, ssbt.Strategy, ssbt.data, ssbt.execution, ssbt.analytics
related_pages: /docs/index.md, /docs/use-cases/index.md
---

## Stable API Domains

| Module | Reference Document | Description |
| :--- | :--- | :--- |
| **Core Engine & Strategy** | [core.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/core.md) | `Engine`, `Strategy`, `Order`, `Fill`, `Trade`, `BacktestResult` |
| **Data Feeds & PIT Joins** | [feeds.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/feeds.md) | `InMemoryFeed`, `ParquetFeed`, `align_multi_timeframe`, `rebuild_orderbook_from_bars` |
| **Execution Engines** | [execution.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/execution.md) | `MatchingEngine`, `RealisticExecutionEngine`, `L3MatchingEngine` |
| **Microstructure Models** | [microstructure.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/microstructure.md) | `ImpactModel`, `LiquidityCapModel`, `BorrowCostModel` |
| **Risk & Capacity** | [risk_capacity.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/risk_capacity.md) | `StrategyCapacityAnalyzer`, `VolatilityTargetingOverlay` |
| **Overfitting & Stats** | [stats_overfitting.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/stats_overfitting.md) | `deflated_sharpe_ratio`, `probability_of_backtest_overfitting`, `monte_carlo_trade_permutation` |
| **Audit & Reproducibility** | [audit_repro.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/audit_repro.md) | `AuditLogger`, `capture_environment_snapshot` |
| **Streaming & IPC** | [streaming_ipc.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/streaming_ipc.md) | `ExecutionStreamPublisher`, `SocketIPCSink`, `RingBufferIPCSink` |
| **CLI & Rerun Engine** | [cli.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/cli.md) | `ssbt.cli.rerun`, `ssbt run`, `ssbt validate` |
