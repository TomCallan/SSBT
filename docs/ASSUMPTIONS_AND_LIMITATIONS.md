# SSBT Assumptions and Limitations Reference

This document provides explicit details regarding the physical, mathematical, and execution assumptions built into the SSBT engine, as well as current boundaries and limitations.

---

## 1. Execution & Fill Model Assumptions

1. **Intrabar Price Path Progression**: Limit and Stop orders simulate realistic intrabar progression (`Open` $\rightarrow$ `High`/`Low` $\rightarrow$ `Close`). Fills occur strictly when price bounds are touched or crossed.
2. **Order Slippage & Commission**: Market orders incur a default 1 bps base slippage and 1 bps commission fee unless overridden in `RealisticExecutionEngine`.
3. **Liquidity Participation Caps**: Default order participation per bar is capped at $\le 10\%$ of bar Average Daily Volume (ADV). Orders exceeding participation thresholds are partially filled.
4. **Short Position Borrow Costs**: Short positions incur an annualized borrow fee (default 1.0% per annum) calculated on a daily pro-rata basis.

---

## 2. Point-In-Time & Data Integrity

1. **Timestamp Monotonicity**: Feeds require monotonically non-decreasing integer nanosecond timestamps.
2. **Multi-Timeframe Joins**: Higher timeframe features (e.g. daily trend filters joining to hourly bars) use completed prior bar timestamps only (`shift(1)`), preventing same-bar lookahead.
3. **Fail-Closed Causality**: The `AuditLogger` verifies event and fill ordering. Any negative time delta or future lookahead raises a `CausalityViolationError` and fails the backtest run.

---

## 3. Statistical Overfitting Defense

1. **Deflated Sharpe Ratio (DSR)**: Adjusts observed Sharpe ratio for multiple testing trials ($N$), Sharpe variance, skewness, and kurtosis. DSR $> 0.95$ indicates high statistical confidence.
2. **Probability of Backtest Overfitting (PBO)**: Evaluates parameter matrix returns across 50 In-Sample vs Out-of-Sample permutations. PBO $> 0.50$ flags high overfitting risk.
3. **Monte Carlo Resampling**: Bootstraps 1,000 trade sequence permutations to compute non-parametric 95% confidence bounds on final equity and maximum drawdown.

---

## 4. Current Engine Boundaries & Limitations

1. **Intrabar Tick Order**: Single-bar simulation assumes tick path proceeds `Open` $\rightarrow$ `High`/`Low` $\rightarrow$ `Close`. Order fill ordering within a single bar depends on this path approximation.
2. **Single Currency Base**: Portfolio accounting operates in USD base currency. Cross-currency FX conversion models require external price adjustment.
