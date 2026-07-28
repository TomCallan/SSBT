# SSBT Quantitative Research & Exploration Engine - Agent Instructions

## Current Status
- **Branch**: `dev-generic-exploration-engine-plan`
- **Goal**: Generic event-driven exploration engine & backtester with real-time IPC streaming, anti-lookahead auditing, overfitting defense (DSR/PBO), market microstructure realism (partial fills, worst-case execution), reproducibility rerun system, and GUI integration.
- **Progress**: M0-M7 COMPLETE (100%) + Institutional Quant Hardening COMPLETE (100%) + Quant Due-Diligence Checklist COMPLETE (100%).

## Milestone Status
```
M0 [X] 100% Baseline Preservation
M1 [X] 100% Spec Foundation  
M2 [X] 100% Plugin Contracts
M3 [X] 100% Vertical Slice
M4 [X] 100% Statistical Confidence & DSR/PBO Overfitting Defense
M5 [X] 100% Reporting Suite & Visual Charts
M6 [X] 100% Backtesting Integration & Prop Engine
M7 [X] 100% Hardening, Orderbook Engine, Partial Fills, Rerun Engine & Real-Time IPC Stream
```

## Key Architectural Principles & Controls
1. Zero Emojis Rule: Strictly maintain clean text/markdown across all code, logs, and docs.
2. Data Ingestion Philosophy: SSBT harnesses zero internal data downloading APIs; external data is supplied as Polars DataFrames into `InMemoryFeed`.
3. Worst-Case Adverse Execution: Pending orders match in conservative order ("fills against position then for"), evaluating stop-loss orders prior to profit target fills.
4. Orderbook Engine & Partial Fills: Reconstruct synthetic L2 depth quotes (`rebuild_orderbook_from_bars`) and support `OrderStatus.PARTIALLY_FILLED`.
5. Anti-Lookahead Causality & Point-In-Time Integrity: Validate timestamp causality using `AuditLogger`, `align_multi_timeframe()`, and emit SHA-256 integrity signatures and `simulation_assumptions_report.json`.
6. Immutable Reproducibility: Capture environment snapshots (`environment_snapshot.json`) and verify 100% deterministic rerun fidelity using `uv run python -m ssbt.cli.rerun <run_id>`.
7. Statistical Overfitting Defense: Calculate Deflated Sharpe Ratio (`deflated_sharpe_ratio`), Probability of Backtest Overfitting (`probability_of_backtest_overfitting`), and Monte Carlo trade sequence permutations.
8. Zero-Allocation Loops: Leverage Polars Arrow memory and Numba pre-allocated bar loops for high-throughput backtesting (>1,000,000 bars/sec).

## Key Package APIs
- Core Strategy Base: `from ssbt import Strategy, Side, Order, OrderType, OrderStatus, Bar`
- Position Helpers: `self.is_flat(engine, symbol)`, `self.get_position_qty(engine, symbol)`
- Orderbook & Partial Fills: `from ssbt import rebuild_orderbook_from_bars, OrderBookFeed, OrderBookQuote`
- Reproducibility & Rerun: `from ssbt import capture_environment_snapshot`, `python -m ssbt.cli.rerun <artifact_dir>`
- Point-In-Time Alignment: `from ssbt import align_multi_timeframe, validate_point_in_time_join`
- Overfitting Defense: `from ssbt import deflated_sharpe_ratio, probability_of_backtest_overfitting, monte_carlo_trade_permutation`
- Microstructure Realism: `from ssbt import ImpactModel, LiquidityCapModel, BorrowCostModel, RealisticExecutionEngine`
- Risk & Capacity: `from ssbt import VolatilityTargetingOverlay, StrategyCapacityAnalyzer`
- Backtest Adapter: `from ssbt import BacktestAdapter, InMemoryFeed`
- Causal Audit Logger: `from ssbt import AuditLogger`
- Real-Time IPC Stream: `from ssbt import ExecutionStreamPublisher, StreamEvent`

## Testing Commands
```bash
# Run full pytest suite (147 unit & integration tests)
uv run python -m pytest ssbt/tests/ -v

# Run synthetic L2 orderbook reconstruction example
uv run python examples/orderbook_reconstruction_example.py

# Run deterministic rerun CLI verifier
uv run python -m ssbt.cli.rerun artifacts/inst_run_20260728_211537

# Run institutional due-diligence verification suite
uv run python examples/institutional_due_diligence_suite.py

# Run multi-ticker & multi-timeframe prop matrix suite
uv run python examples/multi_ticker_timeframe_suite.py

# Run interactive Tkinter Desktop GUI
uv run python gui_examples/desktop_gui.py

# Run interactive Web Browser Dashboard GUI
uv run python gui_examples/web_gui.py
```
