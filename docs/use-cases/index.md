# SSBT Use Cases Registry

---
summary: Master index of outcome-focused SSBT quantitative use cases with standardized templates and runnable examples.
keywords: use cases, mean reversion, point in time, live streaming, microstructure, capacity, overfitting defense, rerun audit, strategy comparison
domain: quantitative-finance
difficulty: intermediate-to-advanced
primary_apis: ssbt.Strategy, ssbt.Engine, ssbt.data, ssbt.analytics, ssbt.execution
related_pages: /docs/index.md, /docs/use-cases/index.yaml, /docs/architecture/index.md
---

This directory contains concrete, outcome-first quantitative research and execution workflows built on SSBT.

## Concrete Use Cases

| Use Case | Objective | Primary APIs | Runtime Profile |
| :--- | :--- | :--- | :--- |
| **[Single-Asset Mean Reversion](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/single-asset-mean-reversion.md)** | Trade rolling Z-score mean reversion with ATR trailing stops. | `ssbt.Strategy`, `OrderType.LIMIT` | `fast` |
| **[Multi-Timeframe Signal Alignment](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/multi-timeframe-signal-alignment.md)** | Align multi-frequency bar streams with zero lookahead bias. | `align_multi_timeframe`, `validate_point_in_time_join` | `balanced` |
| **[Event-Driven Live Streaming](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/event-driven-live-streaming.md)** | Stream real-time execution events over IPC sockets/ring buffers. | `ExecutionStreamPublisher`, `SocketIPCSink` | `max_fidelity` |
| **[Market Microstructure Stress Test](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/market-microstructure-stress-test.md)** | Test strategies against synthetic L2 depth and partial fills. | `rebuild_orderbook_from_bars`, `OrderBookEngine` | `max_fidelity` |
| **[Capacity and Impact Study](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/capacity-and-impact-study.md)** | Estimate max AUM under square-root market impact & participation caps. | `StrategyCapacityAnalyzer`, `ImpactModel` | `balanced` |
| **[Overfitting Defense Workflow](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/overfitting-defense-workflow.md)** | Calculate Deflated Sharpe Ratio (DSR), PBO, and Monte Carlo permutations. | `deflated_sharpe_ratio`, `probability_of_backtest_overfitting` | `fast` |
| **[Deterministic Rerun and Audit](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/deterministic-rerun-and-audit.md)** | Audit causality and verify 100% bitwise rerun reproducibility. | `AuditLogger`, `python -m ssbt.cli.rerun` | `fast` |
| **[Strategy Comparison Lab](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/strategy-comparison-lab.md)** | Compare multi-strategy portfolios with out-of-sample Walk-Forward validation. | `ssbt.service.compare`, `WalkForwardOptimizer` | `balanced` |

---

## Strict Page Template Structure
Every use case document strictly adheres to the following 8-part layout:
1. **Objective**: Crisp statement of the quantitative or operational outcome.
2. **Inputs**: Required data schemas, frequency, and parameters.
3. **Minimal Code**: Minimal self-contained Python script implementing the workflow.
4. **Realistic Settings**: Production-grade execution models, fee schedules, and constraints.
5. **Expected Artifacts**: Directory structure and JSON/Parquet outputs.
6. **Failure Modes**: Common errors, lookahead risks, or convergence issues.
7. **Validation Checks**: Concrete assertions verifying correctness.
8. **Production Checklist**: Final verification steps before deployment.
