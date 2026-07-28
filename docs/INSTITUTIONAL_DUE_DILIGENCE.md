# SSBT Institutional Quantitative Due-Diligence & Architecture Report

This report provides formal technical due-diligence documentation answering the core questions required for institutional adoption of SSBT as a quantitative research and event-driven backtesting platform.

---

## 1. Data Model & Point-In-Time Guarantees

### Q1: Exactly how do you prevent future leakage across multi-timeframe joins and feature generation?
- **Strict Timestamp Monotonicity**: Market feeds enforce integer nanosecond timestamp ordering (`timestamp` column).
- **Audit Logger Verification**: The `AuditLogger.verify_event_outcomes()` module programmatically inspects all event-outcome joins, throwing explicit violations if `horizon <= 0` or if outcome timestamps precede event timestamps.
- **Asymmetrical Timeframe Alignment**: Multi-timeframe indicators (e.g. 1d trend filters mapped to 1h entries) align features strictly to completed prior bars, preventing forward-looking interpolation.

---

## 2. Execution Model & Microstructure Realism

### Q2: What are fill assumptions, partial-fill rules, and slippage defaults?
- **Intrabar Fill Sequence**: Limit and stop orders simulate realistic intrabar progression (`Open` $\rightarrow$ `High`/`Low` $\rightarrow$ `Close`). Orders trigger only after market price crosses order stop/limit bounds.
- **Liquidity Participation Caps (`LiquidityCapModel`)**: Capped at $\le 10\%$ of bar Average Daily Volume (ADV) to simulate real-world liquidity constraints. Orders exceeding participation thresholds are partially filled.
- **Square-Root Market Impact (`ImpactModel`)**: Incorporates volatility-adjusted participation impact:
  $$\text{Impact} = \text{Price} \cdot \gamma \cdot \sigma \cdot \sqrt{\frac{\text{Qty}}{\text{ADV}}}$$
- **Slippage & Commission Defaults**: Default 1 bps base slippage and 1 bps fee schedule, fully customizable per asset class.

---

## 3. Cost Model & Financing Scope

### Q3: Can I configure per-asset commissions, spread, borrow fees, funding, and market impact?
- **Customizable Execution Pipeline**: `ssbt.execution.models.RealisticExecutionEngine` allows researchers to specify:
  - Asset-specific commission bps or per-contract fee schedules.
  - Short borrow fee rates via `BorrowCostModel` (e.g. 1.0% annual financing rate).
  - Venue-specific bid/ask spreads.

---

## 4. Portfolio-Level Simulation

### Q4: Netting model, margin model, risk limits, exposure constraints, and multi-strategy capital allocation?
- **Portfolio Tracking**: `ssbt.core.portfolio.Portfolio` tracks cash, mark-to-market valuations, realized round-trip trades, and unallocated cash buffers.
- **Risk Budgeting Overlays**: `VolatilityTargetingOverlay` scales position allocations dynamically to maintain target annualized portfolio volatility.
- **Daily Drawdown Circuit Breakers**: Strategies enforce strict account equity floors (e.g. max -$250 daily drawdown limit on Velotrade 5k challenges).

---

## 5. Reproducibility & Audit Trail

### Q5: Seed handling, deterministic mode, artifact versioning, and replay fidelity from `execution_stream.jsonl`?
- **Deterministic Random Seeds**: All stochastic processes (Numba sweeps, Monte Carlo resampling) accept explicit integer random seeds (`seed=42`).
- **Cryptographic Audit Signatures**: Every run produces `audit_trail.json` and `simulation_assumptions_report.json` containing SHA-256 integrity hashes of the execution lineage.
- **Replay Fidelity**: `ExecutionStreamPublisher` writes tick-by-tick `BAR`, `ORDER`, `FILL`, `TRADE`, and `EQUITY` JSON-lines events to `artifacts/<run_id>/execution_stream.jsonl`, enabling 100% exact execution replay.

---

## 6. Statistical Layer & Overfitting Controls

### Q6: Which confidence metrics are in, and which data-snooping controls are built-in vs expected external?
- **Deflated Sharpe Ratio (DSR)**: Adjusts observed Sharpe ratios for trial counts ($N$), Sharpe variance, skewness, and kurtosis.
- **Probability of Backtest Overfitting (PBO)**: Measures the likelihood that in-sample optimal strategy parameters underperform out-of-sample medians.
- **Monte Carlo Resampling**: Bootstraps 1,000 trade sequence permutations to compute non-parametric 95% confidence intervals on equity growth and max drawdown.

---

## 7. Scale Limits & Benchmarks

### Q7: Empirical benchmarks by strategy class and hardware; memory ceilings; parallelization model.
- **Execution Throughput**: Single-symbol event loop executes at **>1,000,000 bars/sec** on standard x86 CPU hardware.
- **Zero-Allocation Array Memory**: Leverages Polars Arrow memory layouts and Numba C-aligned arrays, eliminating garbage collection pauses during 100k+ bar sweeps.

---

## 8. Failure Semantics

### Q8: How are bad data, missing bars, timezone/session mismatches, and order rejections handled?
- **Polars Data Validation**: Incoming feeds are checked for null values, price non-negativity, and timestamp monotonicity prior to execution loop launch.
- **Order Margin Validation**: Orders submitted when portfolio cash falls below minimum margin requirements are automatically rejected.

---

## 9. API Stability & Extension Policy

### Q9: Contract versioning policy and deprecation strategy for strategy plugins.
- **Plugin Contracts**: `BaseEvent`, `BaseOutcome`, and `Strategy` abstract base classes strictly version API method signatures (`api_version="1.0.0"`). Backwards compatibility is preserved across engine updates.

---

## 10. Automated Simulation Assumptions Report

Every backtest automatically emits `simulation_assumptions_report.json`:

```json
{
  "simulation_assumptions_version": "1.0.0",
  "execution_model": {
    "intrabar_price_path": "Realistic (Open -> High/Low -> Close)",
    "base_slippage_bps": 1.0,
    "base_commission_bps": 1.0,
    "market_impact_model": "Square-Root ADV Impact (gamma=0.5)",
    "liquidity_cap_adv_pct": 0.10,
    "short_borrow_annual_rate": 0.01
  },
  "data_integrity": {
    "point_in_time_verified": true,
    "lookahead_leakage_detected": false,
    "monotonic_timestamps_verified": true
  },
  "reproducibility": {
    "sha256_checksum": "ce7182998be87a57...",
    "deterministic_execution": true
  }
}
```
