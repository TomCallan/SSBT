---
name: ssbt-exploration
description: Interactive skill for executing event studies, strategy backtests, statistical confidence analyses, DSR/PBO overfitting defense, market microstructure impact modeling, real-time IPC event streaming, and audit trail verification with SSBT.
---

# SSBT Skill & Integration Guide for Agentic Assistants

Use this skill when interacting with the **SSBT (Super Speedy Backtesting Tool)** exploration and backtesting engine codebase.

## Capabilities & Workflows

1. **Event Study & Matrix Execution**:
   - Parse or construct YAML experiment specifications.
   - Run experiments using `ssbt.experiments.runner.run_experiment(config_path)`.
   - Run multi-ticker & multi-timeframe strategy matrices using `examples/multi_ticker_timeframe_suite.py`.
   - Inspect generated CSV, Parquet, JSON artifacts and `manifest.json`.

2. **Custom Event & Outcome Plugin Development**:
   - Subclass `ssbt.events.base.BaseEvent` to create new signal triggers.
   - Subclass `ssbt.outcomes.base.BaseOutcome` to measure multi-horizon forward returns or path metrics.
   - Register plugins via `ssbt.experiments.registry.Registry`.

3. **Strategy Backtesting & Position Helpers**:
   - Subclass `ssbt.strategy.base.Strategy`.
   - Use `self.is_flat(engine, symbol)` to check position status before entries.
   - Define `on_bar(bar, engine)` with market, limit, stop, trailing stop, and OCO order submissions.
   - Execute via `ssbt.core.engine.Engine` or `ssbt.backtest.adapter.BacktestAdapter`.

4. **Statistical Overfitting Defense**:
   - Use `ssbt.deflated_sharpe_ratio` (DSR) to adjust observed Sharpe ratios for multiple testing, skewness, and kurtosis.
   - Use `ssbt.probability_of_backtest_overfitting` (PBO) to evaluate parameter sweep overfitting risk.
   - Use `ssbt.monte_carlo_trade_permutation` to calculate 95% confidence intervals on equity growth and max drawdown.

5. **Market Microstructure & Capacity Modeling**:
   - Use `ssbt.execution.models.ImpactModel` for square-root market impact.
   - Use `ssbt.execution.models.LiquidityCapModel` for ADV participation caps.
   - Use `ssbt.portfolio.risk.StrategyCapacityAnalyzer` to estimate strategy max AUM capacity.

6. **Real-Time IPC Execution Stream**:
   - Use `ssbt.analytics.stream.ExecutionStreamPublisher` to stream events to `artifacts/<run_id>/execution_stream.jsonl`.
   - Attach subscriber callbacks to integrate with live PySide/Tkinter/Web GUIs (`gui_examples/desktop_gui.py` and `gui_examples/web_gui.py`).

7. **Integrity & Audit Trail Verification**:
   - Use `ssbt.analytics.audit.AuditLogger` to run anti-lookahead timestamp checks (`verify_event_outcomes`, `verify_backtest`).
   - Export mathematical audit trails (`audit_trail.json` and `simulation_assumptions_report.json` with SHA-256 signatures).

8. **Terminal Displays & Standard Charts**:
   - Use `ssbt.analytics.terminal.display_experiment_summary(result)` to render rich terminal tables.
   - Use `ssbt.analytics.terminal.display_backtest_summary(metrics, trades)` for strategy performance.
   - Use `ssbt.analytics.terminal.display_audit_status(report)` to verify causal integrity.
   - Use `generate_matrix_heatmap_chart()` and `generate_multi_equity_curve_chart()` for standard visual plots.

## Testing Commands
```bash
# Run complete test suite (142 unit & integration tests)
uv run python -m pytest ssbt/tests/ -v

# Run institutional due-diligence verification suite
uv run python examples/institutional_due_diligence_suite.py

# Run multi-ticker & multi-timeframe prop matrix suite
uv run python examples/multi_ticker_timeframe_suite.py

# Run interactive Tkinter Desktop GUI
uv run python gui_examples/desktop_gui.py

# Run interactive Web Dashboard GUI
uv run python gui_examples/web_gui.py
```
