---
name: ssbt-exploration
description: Interactive skill for executing event studies, L2 orderbook depth reconstruction, partial fill execution, strategy backtests, statistical confidence analyses, DSR/PBO overfitting defense, market microstructure impact modeling, real-time IPC event streaming, and audit trail verification with SSBT.
---

# SSBT Skill & Integration Guide for Agentic Assistants

Use this skill when interacting with the **SSBT (Super Speedy Backtesting Tool)** exploration and backtesting engine codebase.

## Capabilities & Workflows

1. **External Data Ingestion Paradigm**:
   - SSBT harnesses zero internal data downloading APIs.
   - All market data (CSV, Parquet, CCXT, SQL) must be converted into Polars DataFrames and provided to `InMemoryFeed` or `ParquetFeed`.

2. **Orderbook Engine & Synthetic L2 Reconstruction**:
   - Reconstruct synthetic L2 multi-level depth quotes from minute/hourly bar data using `ssbt.data.orderbook.rebuild_orderbook_from_bars(bar_df, spread_pct, depth_levels)`.
   - Run depth matching and partial fills against orderbook liquidity queues.

3. **Worst-Case Adverse Execution Ordering**:
   - Matching engine evaluates pending orders in conservative order ("fills against position then for"), matching adverse stop-loss and trailing stops before profit-taking limit fills.

4. **Strategy Backtesting & Position Helpers**:
   - Subclass `ssbt.strategy.base.Strategy`.
   - Use `self.is_flat(engine, symbol)` to check position status before entries.
   - Define `on_bar(bar, engine)` with market, limit, stop, trailing stop, and OCO order submissions.
   - Execute via `ssbt.core.engine.Engine` or `ssbt.backtest.adapter.BacktestAdapter`.

5. **Statistical Overfitting Defense**:
   - Use `ssbt.deflated_sharpe_ratio` (DSR) to adjust observed Sharpe ratios for multiple testing, skewness, and kurtosis.
   - Use `ssbt.probability_of_backtest_overfitting` (PBO) to evaluate parameter sweep overfitting risk.
   - Use `ssbt.monte_carlo_trade_permutation` to calculate 95% confidence intervals on equity growth and max drawdown.

6. **Immutable Deterministic Reproducibility**:
   - Capture environment metadata (`environment_snapshot.json`).
   - Run `uv run python -m ssbt.cli.rerun <artifact_dir>` to verify 100% exact rerun fidelity.

7. **Real-Time IPC Execution Stream**:
   - Use `ssbt.analytics.stream.ExecutionStreamPublisher` to stream events to `artifacts/<run_id>/execution_stream.jsonl`.
   - Attach subscriber callbacks to integrate with live PySide/Tkinter/Web GUIs (`gui_examples/desktop_gui.py` and `gui_examples/web_gui.py`).

8. **Integrity & Audit Trail Verification**:
   - Use `ssbt.analytics.audit.AuditLogger` to run anti-lookahead timestamp checks (`verify_event_outcomes`, `verify_backtest`).
   - Export mathematical audit trails (`audit_trail.json` and `simulation_assumptions_report.json` with SHA-256 signatures).

## Testing Commands
```bash
# Run complete test suite (147 unit & integration tests)
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
