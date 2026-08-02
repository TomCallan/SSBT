# SSBT Quantitative Research & Exploration Engine

---
summary: Canonical root documentation for SSBT quantitative research and event-driven backtesting engine.
keywords: ssbt, backtesting, quantitative research, market microstructure, point-in-time alignment, overfitting defense, determinism
domain: quantitative-finance
difficulty: beginner-to-advanced
primary_apis: ssbt.Engine, ssbt.Strategy, ssbt.quick_backtest, ssbt.InMemoryFeed
related_pages: /docs/quickstart/index.md, /docs/use-cases/index.md, /docs/architecture/index.md, /docs/reference/index.md
---

## Mission Statement
SSBT is a high-performance, event-driven, market-accurate backtesting engine and generic strategy exploration framework designed for institutional quantitative research. It delivers point-in-time integrity, market microstructure realism, statistical overfitting defenses, and 100% deterministic reproducibility.

## What SSBT Is vs. What SSBT Is Not

| SSBT Is | SSBT Is Not |
| :--- | :--- |
| **Event-driven, point-in-time backtesting engine** with zero lookahead bias. | An automated live trading broker execution adapter. |
| **Zero data-dependency engine** consuming Polars DataFrames and tick streams. | A historical market data scraper or downloader client. |
| **Microstructure-realistic simulator** enforcing partial fills, participation caps, and square-root impact. | A simplified vectorised backtester ignoring order book dynamics and execution friction. |
| **Statistical overfitting defense suite** incorporating DSR, PBO, and Monte Carlo trade permutations. | A curve-fitting parameter miner that reports uncorrected in-sample Sharpe ratios. |
| **Deterministic rerun environment** verifying SHA-256 state and environmental integrity. | A non-reproducible black box backtester with hidden stochastic state. |

## Scope Freeze Notice
> **HARD SCOPE FREEZE**: The SSBT core feature set is fully completed and locked. All current and future development focuses exclusively on UX ergonomics, documentation clarity, error handling, performance tuning, and API refinement.

---

## Three Parallel Entry Points

### 1. By Objective (What You Want to Achieve)
* [Run a minimal 5-minute backtest](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/quickstart/5-minute-run.md)
* [Execute a microstructure stress test with partial fills](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/market-microstructure-stress-test.md)
* [Evaluate strategy capacity and market impact](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/capacity-and-impact-study.md)
* [Calculate Deflated Sharpe Ratio & PBO](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/overfitting-defense-workflow.md)
* [Audit point-in-time causality & run deterministic rerun](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/deterministic-rerun-and-audit.md)
* [Stream events live into a GUI via IPC](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/event-driven-live-streaming.md)

### 2. By Role
* **Quantitative Researcher**: Focus on [Overfitting Defense](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/overfitting-defense-workflow.md), [Strategy Comparison Lab](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/strategy-comparison-lab.md), and [Statistical Reference](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/stats_overfitting.md).
* **Strategy Engineer**: Focus on [Quickstart Runs](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/quickstart/index.md), [Multi-Timeframe Alignment](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/multi-timeframe-signal-alignment.md), and [Core Reference API](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/core.md).
* **Risk & Institutional Lead**: Focus on [Trust & Validation](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/trust-and-validation/index.md), [Capacity & Impact Study](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/capacity-and-impact-study.md), and [Audit Logger](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/audit_repro.md).
* **Infra / DevOps Engineer**: Focus on [Deterministic Rerun](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/deterministic-rerun-and-audit.md), [Streaming IPC API](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/streaming_ipc.md), and [CLI Reference](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/cli.md).

### 3. By API Surface (Contract Reference)
* [Core Engine & Strategy API (`core.md`)](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/core.md)
* [Data Feeds & PIT Join API (`feeds.md`)](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/feeds.md)
* [Execution Engine API (`execution.md`)](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/execution.md)
* [Microstructure Models API (`microstructure.md`)](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/microstructure.md)
* [Risk & Capacity API (`risk_capacity.md`)](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/risk_capacity.md)
* [Overfitting & Stats API (`stats_overfitting.md`)](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/stats_overfitting.md)
* [Audit & Reproducibility API (`audit_repro.md`)](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/audit_repro.md)
* [Streaming & IPC API (`streaming_ipc.md`)](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/streaming_ipc.md)
* [CLI & Rerun API (`cli.md`)](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/reference/cli.md)

---

## Choose Your Workflow Matrix

| Intent | Recommended Doc Page | Canonical Script Path |
| :--- | :--- | :--- |
| **Fast Strategy Prototyping** | [5-Minute Quickstart](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/quickstart/5-minute-run.md) | `ssbt/quick.py` |
| **Single-Asset Mean Reversion** | [Single-Asset Mean Reversion](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/single-asset-mean-reversion.md) | `strategies_vault/volatility_mean_reversion.py` |
| **Multi-Timeframe Signal Alignment** | [Multi-Timeframe Signal Alignment](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/multi-timeframe-signal-alignment.md) | `ssbt/data/point_in_time.py` |
| **Orderbook & Microstructure Fills** | [Market Microstructure Stress Test](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/market-microstructure-stress-test.md) | `ssbt/data/orderbook.py` |
| **Market Impact & Capacity Analysis** | [Capacity and Impact Study](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/capacity-and-impact-study.md) | `ssbt/portfolio/capacity.py` |
| **DSR / PBO Overfitting Defense** | [Overfitting Defense Workflow](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/overfitting-defense-workflow.md) | `ssbt/analytics/overfitting.py` |
| **Audit Causality & Rerun Engine** | [Deterministic Rerun and Audit](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/deterministic-rerun-and-audit.md) | `ssbt/cli/rerun.py` |
| **Live GUI Streaming** | [Event-Driven Live Streaming](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/use-cases/event-driven-live-streaming.md) | `ssbt/analytics/ipc_stream.py` |

---

## Standardized Vocabulary
All SSBT documentation strictly enforces canonical quantitative terminology:
- **point-in-time alignment**: Sequential merging of multi-frequency bar streams preventing future timestamp leakage.
- **deflated Sharpe ratio**: Sharpe ratio corrected for trial multiplicity, non-normality, and track record length.
- **probability of backtest overfitting**: Probability that the chosen in-sample optimal strategy yields sub-median out-of-sample performance.
- **partial fills**: Order execution matching available book volume rather than filling orders atomically.
- **worst-case adverse execution**: Matching pending orders against position direction first and evaluating stop-loss orders prior to profit target fills.
