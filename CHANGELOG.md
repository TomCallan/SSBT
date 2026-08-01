# Changelog

All notable changes to SSBT are documented here.

## [0.5.0] - 2026-07-31

### Added
- Real-time IPC streaming: `ExecutionStreamPublisher`, `StreamEvent`, multiple sink backends
- Orderbook engine: `rebuild_orderbook_from_bars`, `OrderBookEngine`, `OrderBookFeed`, L2 depth reconstruction
- Universal tick stream: `UniversalTickStream`, `UniversalTickFeed`, `GenericTickEvent`
- Anti-lookahead audit: `AuditLogger`, SHA-256 integrity signatures, `simulation_assumptions_report.json`
- Point-in-time alignment: `align_multi_timeframe`, `validate_point_in_time_join`, `CausalityViolationError`
- Overfitting defense: `deflated_sharpe_ratio`, `probability_of_backtest_overfitting`, `monte_carlo_trade_permutation`
- Microstructure realism: `ImpactModel`, `LiquidityCapModel`, `BorrowCostModel`, `RealisticExecutionEngine`
- Risk & capacity: `VolatilityTargetingOverlay`, `StrategyCapacityAnalyzer`
- Reproducibility rerun: `capture_environment_snapshot`, `environment_snapshot.json`, `python -m ssbt.cli.rerun <run_id>`
- Service layer: `run_backtest`, `run_backtest_async`, `rerun`, `compare`, job management APIs
- Partial fills: `OrderStatus.PARTIALLY_FILLED`, synthetic L2 depth quote matching
- PEP 561 `py.typed` marker (inline type annotations declared)

## [0.3.0] - earlier

### Added
- Backtesting engine: `Engine`, `BacktestResult`, `MultiSymbolEngine`
- Walk-forward optimizer: `WalkForwardOptimizer`
- Exploration framework: `Registry`, `BaseEvent`, `BaseOutcome`, `BacktestAdapter`
- Reporting suite: equity curve, drawdown, trade, and dashboard plots
- DSR/PBO statistical overfitting defense (initial)
