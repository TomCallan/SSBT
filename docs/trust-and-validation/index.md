# Trust, Causality & Validation Documentation

---
summary: Institutional due diligence documentation covering anti-lookahead controls, statistical overfitting defenses (DSR/PBO), Monte Carlo resampling, reproducibility guarantees, and model risk assumptions.
keywords: trust, causality, anti-lookahead, DSR, PBO, Monte Carlo, reproducibility, assumptions report, model risk
domain: quantitative-compliance
difficulty: advanced
primary_apis: ssbt.analytics.AuditLogger, ssbt.analytics.deflated_sharpe_ratio, ssbt.cli.rerun
related_pages: /docs/index.md, /docs/INSTITUTIONAL_DUE_DILIGENCE.md, /docs/ASSUMPTIONS_AND_LIMITATIONS.md
---

## 1. Anti-Lookahead Controls & Causality Verification

SSBT enforces strict point-in-time causality boundaries:
- **Timestamp Monotonicity**: Bar events are processed in strictly non-decreasing timestamp order ($ t_i \ge t_{i-1} $).
- **Point-In-Time Joins**: Multi-frequency indicators are merged via `align_multi_timeframe()` using backward `asof` matching.
- **Audit Logger**: `AuditLogger` emits SHA-256 state hashes per tick to verify zero future data leakage.

## 2. Statistical Overfitting Defense Guidelines

| Metric | Formula / Method | Institutional Pass Threshold |
| :--- | :--- | :--- |
| **Deflated Sharpe Ratio (DSR)** | Adjusts for trial multiplicity ($ N $), skewness, and kurtosis | $ p \text{-value} \le 0.05 $ |
| **Probability of Backtest Overfitting (PBO)** | Combinatorial Purged Cross-Validation (CSCV) | $ PBO < 25.0\% $ |
| **Monte Carlo Permutation** | Trade order resampling (1,000 runs) | 5th percentile Max DD within risk limit |

## 3. Reproducibility Guarantees & Non-Guarantees

### What SSBT Guarantees:
- **100% Bitwise Rerun Determinism**: Identical feed data + identical RNG seed yields bit-for-bit identical trades, fills, and equity curves.
- **Environment Verification**: Captured via `capture_environment_snapshot()`.

### What SSBT Does Not Guarantee:
- Strategy code containing unseeded Python `random` calls or non-deterministic external IO.
- Runs across different floating-point hardware microarchitectures (e.g. x86_64 vs ARM64) without fixed precision mode.

## 4. Execution Realism & Model Risk Statements

- **Intrabar Price Path Assumption**: Standard bar matching assumes price moves `Open -> High -> Low -> Close` (or `Open -> Low -> High -> Close`).
- **Worst-Case Adverse Execution**: Stop-loss fills take priority over take-profit target fills on the same bar.
- **Orderbook Depth Limits**: Fills are constrained by synthetic L2 book volume.
