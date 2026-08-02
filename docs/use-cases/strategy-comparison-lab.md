# Strategy Comparison Lab

---
summary: Comparing multi-strategy portfolios, parameter sweeps, and out-of-sample Walk-Forward performance.
keywords: strategy comparison, parameter sweep, walk forward, multi-strategy, comparative lab
domain: quantitative-research
difficulty: intermediate
primary_apis: ssbt.service.compare, ssbt.optimization.WalkForwardOptimizer, ssbt.analytics.plot_strategy_dashboard
related_pages: /docs/use-cases/index.md, /docs/reference/core.md, /docs/cookbook/index.md
---

## 1. Objective
Compare multiple trading strategies or parameter variants side-by-side using standardized metric deltas, out-of-sample Walk-Forward optimization windows, and unified visualization dashboards.

## 2. Inputs
- Array of strategy instances or strategy configurations
- Historical bar feed covering training and out-of-sample evaluation periods

## 3. Minimal Code

```python
from ssbt import Engine, InMemoryFeed, generate_synthetic_bars
from ssbt.service import compare
from ssbt.optimization import WalkForwardOptimizer, IntParam, ParamRange
from ssbt.quick import sma_cross

df = generate_synthetic_bars(num_bars=3000, start_price=100.0, volatility=0.015, seed=42)
feed = InMemoryFeed({"BTC-USD": df})

# 1. Compare multiple strategy runs via ssbt.service API
comp_result = compare(
    strategies=[sma_cross],
    feed=feed,
    initial_cash=100_000.0
)

print(f"Comparison Summary: {comp_result.summary_metrics}")

# 2. Run Walk-Forward Out-of-Sample Optimizer
wf_optimizer = WalkForwardOptimizer(
    train_bars=1000,
    val_bars=500,
    step_bars=250
)
wf_result = wf_optimizer.run(feed=feed, strategy_cls=sma_cross)
print(f"Walk-Forward Out-Of-Sample Sharpe: {wf_result.out_of_sample_sharpe:.2f}")
```

## 4. Realistic Settings
- **Walk-Forward Windows**: 60% Train, 20% Validation, 20% Out-of-Sample Test.
- **Metric Comparison**: Sharpe Ratio, Sortino Ratio, Max Drawdown, Calmar Ratio, and Win Rate.

## 5. Expected Artifacts
```
artifacts/comparison_lab/
├── comparison_summary.json
├── walk_forward_report.json
└── multi_strategy_equity.png
```

## 6. Failure Modes
- **In-Sample Overfitting**: Selecting optimal parameters without evaluating out-of-sample degradation.
- **Window Overlap Leakage**: Failing to purge overlapping trade sequences between train and test windows.

## 7. Validation Checks
```python
assert comp_result is not None, "Strategy comparison failed to produce result"
assert wf_result.out_of_sample_sharpe is not None, "Walk-forward evaluation failed"
```

## 8. Production Checklist
- [ ] Ensure out-of-sample window sizes reflect real-world rebalancing frequencies.
- [ ] Plot strategy correlation matrix to ensure diversification benefits across strategies.
