# Overfitting Defense Workflow

---
summary: Evaluating statistical overfitting risk using Deflated Sharpe Ratio (DSR), Probability of Backtest Overfitting (PBO), and Monte Carlo trade sequence permutations.
keywords: overfitting defense, deflated sharpe ratio, pbo, monte carlo, multiple testing, quantitative due diligence
domain: statistical-finance
difficulty: advanced
primary_apis: ssbt.analytics.deflated_sharpe_ratio, ssbt.analytics.probability_of_backtest_overfitting, ssbt.analytics.monte_carlo_trade_permutation
related_pages: /docs/use-cases/index.md, /docs/reference/stats_overfitting.md, /docs/trust-and-validation/index.md
---

## 1. Objective
Protect against false discoveries and backtest curve-fitting by adjusting in-sample Sharpe ratios for multiple testing trials ($ N $), returns skewness/kurtosis via Deflated Sharpe Ratio (DSR), and computing Probability of Backtest Overfitting (PBO).

## 2. Inputs
- Daily return series or trade PnL array
- **Parameters**: `num_trials=50`, `track_record_length=N`, `num_slices=10`

## 3. Minimal Code

```python
import numpy as np
import polars as pl
from ssbt.analytics import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    monte_carlo_trade_permutation
)

# Generate sample return series (252 daily returns)
np.random.seed(42)
returns = np.random.normal(loc=0.0005, scale=0.01, size=500)

# 1. Deflated Sharpe Ratio (DSR)
dsr_stat, p_value = deflated_sharpe_ratio(
    returns=returns,
    num_trials=50,             # Number of parameter configurations tested
    track_record_length=len(returns)
)

# 2. Probability of Backtest Overfitting (PBO)
pbo_value = probability_of_backtest_overfitting(
    returns=returns,
    num_slices=10
)

# 3. Monte Carlo Trade Permutations
mc_summary = monte_carlo_trade_permutation(
    returns=returns,
    num_permutations=1000
)

print(f"Deflated Sharpe Ratio (DSR): {dsr_stat:.4f}")
print(f"DSR Significance (p-value): {p_value:.4f}")
print(f"Probability of Backtest Overfitting (PBO): {pbo_value:.2%}")
print(f"Monte Carlo 5th Percentile Max Drawdown: {mc_summary.max_drawdown_p05:.2%}")
```

## 4. Realistic Settings
- **Confidence Cutoff**: Accept strategies only if $ DSR\_p \le 0.05 $ and $ PBO < 25.0\% $.
- **Trial Counter**: Track cumulative parameter iterations across grid search runs.

## 5. Expected Artifacts
```
artifacts/overfitting_defense/
├── overfitting_report.json
└── pbo_distribution.png
```

## 6. Failure Modes
- **Uncounted Trials**: Reporting DSR with `num_trials=1` when 1,000 combinations were swept; severely underestimates overfitting.
- **Non-Stationary Returns**: Heavy-tailed asset returns require kurtosis correction included in DSR formula.

## 7. Validation Checks
```python
assert 0.0 <= pbo_value <= 1.0, "PBO must be bounded between 0 and 1"
assert 0.0 <= p_value <= 1.0, "DSR p-value must be bounded between 0 and 1"
```

## 8. Production Checklist
- [ ] Record exact count of all parameter combinations evaluated ($ N_{trials} $).
- [ ] Verify PBO is below institutional 25% threshold.
- [ ] Export `overfitting_report.json` into institutional due diligence package.
