---
name: ssbt-exploration
description: Interactive skill for executing event studies, strategy backtests, statistical confidence analyses, and audit trail verification with SSBT.
---

# SSBT Skill & Integration Guide for Agentic Assistants

Use this skill when interacting with the **SSBT (Super Speedy Backtesting Tool)** exploration and backtesting engine codebase.

## Capabilities & Workflows

1. **Event Study Execution**:
   - Parse or construct YAML experiment specifications.
   - Run experiments using `ssbt.experiments.runner.run_experiment(config_path)`.
   - Inspect generated CSV, Parquet, JSON artifacts and `manifest.json`.

2. **Custom Event & Outcome Plugin Development**:
   - Subclass `ssbt.events.base.BaseEvent` to create new signal triggers.
   - Subclass `ssbt.outcomes.base.BaseOutcome` to measure multi-horizon forward returns or path metrics.
   - Register plugins via `ssbt.experiments.registry.Registry`.

3. **Strategy Backtesting**:
   - Subclass `ssbt.strategy.base.Strategy`.
   - Define `on_bar(bar, engine)` with market, limit, stop, trailing stop, and OCO order submissions.
   - Execute via `ssbt.core.engine.Engine` or `ssbt.backtest.adapter.BacktestAdapter`.

4. **Integrity & Audit Trail Verification**:
   - Use `ssbt.analytics.audit.AuditLogger` to run anti-lookahead timestamp checks (`verify_event_outcomes`, `verify_backtest`).
   - Export mathematical audit trails (`audit_trail.json`).

5. **Terminal Displays**:
   - Use `ssbt.analytics.terminal.display_experiment_summary(result)` to render rich terminal tables.
   - Use `ssbt.analytics.terminal.display_backtest_summary(metrics, trades)` for strategy performance.
   - Use `ssbt.analytics.terminal.display_audit_status(report)` to verify causal integrity.

## Testing Commands
```bash
# Run complete test suite
uv run python -m pytest ssbt/tests/ -v

# Run experiment CLI runner
uv run python -m ssbt.experiments.runner experiments/volume_spike_study.yaml
```
