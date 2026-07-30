# SSBT Documentation

SSBT is an event-driven quantitative strategy exploration, backtesting, and institutional verification engine written in Python.

This README is the central documentation index for users, researchers, and integrators.

## Table of Contents

- [1. Project Overview](#1-project-overview)
- [2. Scope and Status](#2-scope-and-status)
- [3. Installation](#3-installation)
- [4. Quickstart](#4-quickstart)
- [5. Core Concepts](#5-core-concepts)
- [6. Data Ingestion](#6-data-ingestion)
- [7. Strategy API](#7-strategy-api)
- [8. Backtesting Workflow](#8-backtesting-workflow)
- [9. Execution and Microstructure Realism](#9-execution-and-microstructure-realism)
- [10. Anti-Lookahead and Point-in-Time Integrity](#10-anti-lookahead-and-point-in-time-integrity)
- [11. Overfitting Defense and Statistical Validation](#11-overfitting-defense-and-statistical-validation)
- [12. Reproducibility and Deterministic Reruns](#12-reproducibility-and-deterministic-reruns)
- [13. Real-Time Streaming and IPC](#13-real-time-streaming-and-ipc)
- [14. Visualization and Reporting](#14-visualization-and-reporting)
- [15. Artifacts and Output Structure](#15-artifacts-and-output-structure)
- [16. Performance Characteristics](#16-performance-characteristics)
- [17. CLI Commands](#17-cli-commands)
- [18. Public API Reference](#18-public-api-reference)
- [19. Testing and Verification](#19-testing-and-verification)
- [20. Design Constraints and Guarantees](#20-design-constraints-and-guarantees)
- [21. FAQ](#21-faq)
- [22. Contribution Notes](#22-contribution-notes)
- [23. License and Disclaimer](#23-license-and-disclaimer)

---

## 1. Project Overview

SSBT is designed for quantitative research and production-grade strategy validation. It provides:

- Event-driven simulation and backtesting
- Realistic execution controls (including partial fills and adverse sequencing)
- Overfitting defense metrics (DSR and PBO)
- Causality auditing for anti-lookahead protection
- Immutable rerun workflows for reproducibility
- Real-time event streaming for GUI and external systems

---

## 2. Scope and Status

Current delivery status:

- M0-M7 complete
- Institutional quant hardening complete
- Quant due-diligence checklist complete

Current project policy:

- Feature scope is frozen
- Future work is constrained to:
  - UX refinement
  - API ergonomics
  - Documentation clarity
  - Error handling
  - Performance tuning
  - User value alignment

---

## 3. Installation

SSBT requires Python 3.10+.

```bash
git clone https://github.com/TomCallan/SSBT.git
cd SSBT
uv sync
```

---

## 4. Quickstart

```python
import ssbt

data = ssbt.generate_synthetic_bars(n_bars=1000, seed=42)

@ssbt.strategy
def momentum_strategy(bar, engine):
    if bar.close > bar.open:
        engine.submit_order(
            ssbt.Strategy.market_order(bar.symbol, ssbt.Side.BUY, 1.0)
        )

result = ssbt.quick_backtest(momentum_strategy, data, symbol="BTC-USD", verbose=True)

print(f"Total Return: {result.total_return:.2%}")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
```

---

## 5. Core Concepts

SSBT is built around the following principles:

1. External data ownership: no internal market data downloading API.
2. Causality-first simulation: strict point-in-time and timestamp validity.
3. Conservative execution realism: adverse sequencing and partial fill support.
4. Statistical robustness: overfitting diagnostics are first-class outputs.
5. Reproducibility: deterministic reruns with environment snapshots.

---

## 6. Data Ingestion

All market data is user-supplied as Polars DataFrames.

Primary feeds:

- `InMemoryFeed`
- `ParquetFeed`
- `LiveStreamFeed`
- `UniversalTickFeed`

Required bar schema:

| Column | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | `Int64` | Unix epoch in ms or ns, monotonic |
| `symbol` | `Utf8` | Asset symbol |
| `open` | `Float64` | Open price |
| `high` | `Float64` | High price |
| `low` | `Float64` | Low price |
| `close` | `Float64` | Close price |
| `volume` | `Float64` | Bar volume |

---

## 7. Strategy API

Strategies inherit `Strategy` and implement `on_bar(bar, engine)`.

```python
from ssbt import Strategy, Side, Bar

class MyStrategy(Strategy):
    def on_bar(self, bar: Bar, engine) -> None:
        if self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty=1.0))
```

Position helpers:

- `self.is_flat(engine, symbol)`
- `self.get_position_qty(engine, symbol)`

---

## 8. Backtesting Workflow

```python
import polars as pl
from ssbt import Strategy, Side, Bar, InMemoryFeed, BacktestAdapter, plot

class MovingAverageCross(Strategy):
    def __init__(self, fast=10, slow=30):
        super().__init__()
        self.fast = fast
        self.slow = slow
        self.closes = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        if len(self.closes) < self.slow:
            return
        fast_ma = sum(self.closes[-self.fast:]) / self.fast
        slow_ma = sum(self.closes[-self.slow:]) / self.slow
        if fast_ma > slow_ma and self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty=1.0))
        elif fast_ma < slow_ma and not self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, qty=1.0))

df = pl.DataFrame({
    "timestamp": [1000, 2000, 3000, 4000, 5000],
    "symbol": ["BTC"] * 5,
    "open": [100.0, 102.0, 105.0, 103.0, 108.0],
    "high": [103.0, 106.0, 107.0, 105.0, 110.0],
    "low": [99.0, 101.0, 104.0, 102.0, 107.0],
    "close": [102.0, 105.0, 103.0, 108.0, 112.0],
    "volume": [10.0, 15.0, 12.0, 18.0, 20.0],
})

feed = InMemoryFeed(df, symbol="BTC")
adapter = BacktestAdapter(initial_cash=10000.0)
result = adapter.run_backtest(feed, MovingAverageCross())

plot(result, title="Moving Average Cross Performance")
```

---

## 9. Execution and Microstructure Realism

SSBT supports realistic trade modeling through:

- Worst-case adverse order evaluation
- Partial fills (`OrderStatus.PARTIALLY_FILLED`)
- Orderbook reconstruction (`rebuild_orderbook_from_bars`)
- Impact modeling (`ImpactModel`)
- Liquidity caps (`LiquidityCapModel`)
- Borrow costs (`BorrowCostModel`)
- Realistic execution engine (`RealisticExecutionEngine`)

Adverse sequencing rule:

- Orders are evaluated in conservative priority: fills against the current position before favorable fills, with stop-loss checks prioritized over profit-taking.

---

## 10. Anti-Lookahead and Point-in-Time Integrity

Key tools:

- `AuditLogger`
- `align_multi_timeframe`
- `validate_point_in_time_join`

Example:

```python
from ssbt import AuditLogger

logger = AuditLogger(verbose=False)
report = logger.generate_report(
    backtest_result=result["raw_result"],
    output_dir="artifacts/run_01"
)

print(report.is_valid)
print(report.integrity_hash)
```

Outputs include SHA-256 integrity signatures and simulation assumptions reporting.

---

## 11. Overfitting Defense and Statistical Validation

Built-in functions:

- `deflated_sharpe_ratio`
- `probability_of_backtest_overfitting`
- `monte_carlo_trade_permutation`

Example:

```python
from ssbt import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    monte_carlo_trade_permutation
)

dsr_score = deflated_sharpe_ratio(
    observed_sharpe=2.14,
    var_sharpes=0.20,
    n_trials=10,
    returns_len=252,
)

pbo_score = probability_of_backtest_overfitting(returns_matrix)

mc_results = monte_carlo_trade_permutation(
    trade_pnls=trade_pnls,
    initial_cash=5000.0,
    n_iterations=1000,
)
```

---

## 12. Reproducibility and Deterministic Reruns

SSBT captures:

- Environment metadata
- Configuration fingerprints
- Runtime assumptions
- Deterministic artifacts

Rerun command:

```bash
uv run python -m ssbt.cli.rerun <artifact_dir>
```

Example:

```bash
uv run python -m ssbt.cli.rerun artifacts/inst_run_20260728_211537
```

---

## 13. Real-Time Streaming and IPC

Use `ExecutionStreamPublisher` with sinks for file, socket, or custom listeners.

```python
from ssbt import ExecutionStreamPublisher, BufferedFileSink, SocketIPCSink

publisher = ExecutionStreamPublisher(sinks=[
    BufferedFileSink("artifacts/latest/execution_stream.jsonl", batch_size=500),
    SocketIPCSink(host="127.0.0.1", port=9999)
])
```

Supported stream event categories include bar, order, fill, trade, and equity updates.

---

## 14. Visualization and Reporting

Primary plotting entry points:

- `ssbt.plot(result, title=...)`
- `ssbt.plot_robustness_dashboard(...)`
- `@ssbt.autoplot`

Generated visuals include:

- Equity curves
- Drawdowns
- Performance metrics
- Robustness diagnostics (DSR/PBO/Monte Carlo summaries)

---

## 15. Artifacts and Output Structure

Each run writes a timestamped folder and mirrors it to `artifacts/latest/`.

Representative outputs:

- `audit_trail.json`
- `environment_snapshot.json`
- `execution_stream.jsonl`
- `metrics_overview.json`
- `overfitting_defense_audit.json`
- `simulation_assumptions_report.json`
- `strategy_dashboard.png`
- `robustness_audit.png`
- `trade_log.csv`
- `trade_log.parquet`

---

## 16. Performance Characteristics

- Throughput target: >1,000,000 bars/sec (core loop conditions dependent)
- Memory model: Polars + Apache Arrow zero-copy foundations
- Loop efficiency: pre-allocated Numba-oriented execution paths

---

## 17. CLI Commands

Schema export:

```bash
uv run python -m ssbt schema --out schema.json
```

Strategy validation:

```bash
uv run python -m ssbt validate my_strategy.py
```

Experiment run with machine-readable output:

```bash
uv run python -m ssbt run experiment.yaml --json
```

Deterministic rerun:

```bash
uv run python -m ssbt.cli.rerun <artifact_dir>
```

---

## 18. Public API Reference

```python
from ssbt import (
    Strategy, Side, Order, OrderType, OrderStatus, Bar, Engine, MultiSymbolEngine,
    InMemoryFeed, ParquetFeed, UniversalTickStream, UniversalTickFeed,
    align_multi_timeframe, validate_point_in_time_join,
    BacktestAdapter,
    ImpactModel, LiquidityCapModel, BorrowCostModel, RealisticExecutionEngine,
    VolatilityTargetingOverlay, StrategyCapacityAnalyzer,
    deflated_sharpe_ratio, probability_of_backtest_overfitting, monte_carlo_trade_permutation,
    AuditLogger, capture_environment_snapshot, sync_latest_run_folder, ExecutionStreamPublisher,
    plot, autoplot, plot_strategy_dashboard, plot_robustness_dashboard, plot_performance_metrics,
    SSBTError, DataError, ExecutionError, AuditError,
)
```

---

## 19. Testing and Verification

Run the full test suite:

```bash
uv run python -m pytest ssbt/tests/ -v
```

Deterministic rerun verification:

```bash
uv run python -m ssbt.cli.rerun artifacts/inst_run_20260728_211537
```

---

## 20. Design Constraints and Guarantees

Guaranteed architectural constraints:

1. No internal data downloading API.
2. Conservative adverse execution evaluation.
3. Partial fill realism supported.
4. Point-in-time and anti-lookahead integrity checks.
5. Deterministic rerun pathway.
6. Statistical overfitting diagnostics included by design.

---

## 21. FAQ

### Does SSBT fetch data from brokers or exchanges?
No. Market data must be supplied externally.

### Can I use live data?
Yes. Use `LiveStreamFeed` and push events from your own connectors.

### Does SSBT support anti-lookahead controls?
Yes. Use `AuditLogger`, timestamp validation, and point-in-time alignment utilities.

### How do I validate robustness?
Use DSR, PBO, and Monte Carlo permutation tools provided in the package.

---

## 22. Contribution Notes

Scope is currently frozen for net-new features. Contributions should focus on:

- UX and API quality
- Documentation and examples
- Error handling and resilience
- Performance and profiling
- Test coverage and maintainability

---

## 23. License and Disclaimer

This project is licensed under the MIT License.

SSBT is a quantitative research and backtesting framework for educational and empirical analysis. It is not financial advice and does not guarantee future trading performance.
