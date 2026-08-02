# Overfitting & Statistical Defense API Reference (`ssbt.analytics`)

---
summary: API reference for Deflated Sharpe Ratio (DSR), Probability of Backtest Overfitting (PBO), and Monte Carlo permutations.
keywords: reference, overfitting, deflated sharpe ratio, pbo, monte carlo, stats
domain: api-reference
difficulty: advanced
primary_apis: ssbt.analytics.deflated_sharpe_ratio, ssbt.analytics.probability_of_backtest_overfitting, ssbt.analytics.monte_carlo_trade_permutation
related_pages: /docs/index.md, /docs/reference/index.md, /docs/use-cases/overfitting-defense-workflow.md
---

## `deflated_sharpe_ratio`

Computes Deflated Sharpe Ratio (DSR) corrected for multiple testing trials and skewness/kurtosis.

```python
def deflated_sharpe_ratio(
    returns: np.ndarray,
    num_trials: int,
    track_record_length: int = None
) -> Tuple[float, float]
```
- **Returns**: `(dsr_statistic, p_value)`

---

## `probability_of_backtest_overfitting`

Calculates Probability of Backtest Overfitting (PBO) via Combinatorial Purged Cross-Validation (CSCV).

```python
def probability_of_backtest_overfitting(
    returns: np.ndarray,
    num_slices: int = 10
) -> float
```

---

## `monte_carlo_trade_permutation`

Runs Monte Carlo trade sequence resampling permutations.

```python
def monte_carlo_trade_permutation(
    returns: np.ndarray,
    num_permutations: int = 1000
) -> MonteCarloSummary
```
