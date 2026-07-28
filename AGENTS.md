# SSBT Quantitative Research & Exploration Engine - Agent Instructions

## Current Status
- **Branch**: `dev-generic-exploration-engine-plan`
- **Goal**: Generic event-driven exploration engine & backtester with real-time IPC streaming, anti-lookahead auditing, and GUI integration.
- **Progress**: M0-M7 COMPLETE (100%)

## Milestone Status
```
M0 [X] 100% Baseline Preservation
M1 [X] 100% Spec Foundation  
M2 [X] 100% Plugin Contracts
M3 [X] 100% Vertical Slice
M4 [X] 100% Statistical Confidence
M5 [X] 100% Reporting Suite & Visual Charts
M6 [X] 100% Backtesting Integration & Prop Engine
M7 [X] 100% Hardening, Scale & Real-Time IPC Stream
```

## Key Architectural Principles & Controls
1. Zero Emojis Rule: Strictly maintain clean text/markdown across all code, logs, and docs.
2. Anti-Lookahead Causality: Validate timestamp causality using `AuditLogger` and generate SHA-256 integrity signatures.
3. Zero-Allocation Loops: Leverage Polars Arrow memory and Numba pre-allocated bar loops for high-throughput backtesting (>1,000,000 bars/sec).
4. Real-Time Stream IPC: Stream `BAR`, `ORDER`, `FILL`, `TRADE`, and `EQUITY` events via `ExecutionStreamPublisher` to `artifacts/<run_id>/execution_stream.jsonl` for live GUI integration.

## Key Package APIs
- Core Strategy Base: `from ssbt import Strategy, Side, Order, OrderType, OrderStatus, Bar`
- Position Helpers: `self.is_flat(engine, symbol)`, `self.get_position_qty(engine, symbol)`
- Backtest Adapter: `from ssbt import BacktestAdapter, InMemoryFeed`
- Causal Audit Logger: `from ssbt import AuditLogger`
- Real-Time IPC Stream: `from ssbt import ExecutionStreamPublisher, StreamEvent`
- Standard Charting: `from ssbt import generate_matrix_heatmap_chart, generate_multi_equity_curve_chart`

## Testing Commands
```bash
# Run full pytest suite (133 unit & integration tests)
uv run python -m pytest ssbt/tests/ -v

# Run multi-ticker & multi-timeframe prop matrix suite
uv run python examples/multi_ticker_timeframe_suite.py

# Run interactive Tkinter Desktop GUI
uv run python gui_examples/desktop_gui.py

# Run interactive Web Browser Dashboard GUI
uv run python gui_examples/web_gui.py
```
