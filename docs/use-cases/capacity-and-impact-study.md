# Capacity and Impact Study

---
summary: Estimating strategy maximum capacity (AUM limits) under square-root market impact, liquidity participation caps, and short borrow costs.
keywords: capacity, market impact, square root impact, participation cap, borrow cost, sharpe decay
domain: portfolio-risk
difficulty: advanced
primary_apis: ssbt.portfolio.StrategyCapacityAnalyzer, ssbt.execution.ImpactModel, ssbt.execution.LiquidityCapModel
related_pages: /docs/use-cases/index.md, /docs/reference/risk_capacity.md, /docs/trust-and-validation/index.md
---

## 1. Objective
Quantify Sharpe ratio decay and capacity ceiling ($ AUM_{max} $) as portfolio capital scales under non-linear square-root market impact ($ \eta \cdot \sigma \sqrt{Q / ADV} $) and strict participation caps.

## 2. Inputs
- `BacktestResult` or historical trade sequence
- **Parameters**: `capital_levels=[100k, 1M, 10M, 100M]`, `max_adv_participation=0.05`, `impact_eta=0.1`

## 3. Minimal Code

```python
from ssbt import Engine, InMemoryFeed, generate_synthetic_bars, sma_cross
from ssbt.execution import ImpactModel, LiquidityCapModel, BorrowCostModel, RealisticExecutionEngine
from ssbt.portfolio import StrategyCapacityAnalyzer

df = generate_synthetic_bars(num_bars=5000, start_price=100.0, volatility=0.02, seed=42)
feed = InMemoryFeed({"BTC-USD": df})

# Setup capacity analyzer across capital tiers
analyzer = StrategyCapacityAnalyzer(
    capital_tiers=[100_000, 1_000_000, 10_000_000, 50_000_000],
    impact_model=ImpactModel(eta=0.1),
    liquidity_model=LiquidityCapModel(max_participation=0.05),
    borrow_model=BorrowCostModel(annual_rate=0.01)
)

capacity_report = analyzer.run_study(feed=feed, strategy=sma_cross)

for tier in capacity_report.tiers:
    print(f"Capital: ${tier.capital:,.0f} -> Realized Sharpe: {tier.sharpe_ratio:.2f} (Impact Cost: ${tier.impact_cost:,.2f})")
```

## 4. Realistic Settings
- **Square-Root Impact**: $ \Delta P = \eta \cdot \text{Spread} + \gamma \cdot \sigma \sqrt{\frac{\text{Qty}}{\text{ADV}}} $
- **Short Borrow Fee**: 1.0% per annum calculated daily on short position value.

## 5. Expected Artifacts
```
artifacts/capacity_study/
├── capacity_curve.json
└── sharpe_decay_chart.png
```

## 6. Failure Modes
- **Ignoring ADV Cap**: Orders exceeding 5% ADV causing severe price slippage that turns Sharpe negative.
- **Constant Spread Assumption**: Failing to widen spread during high volatility spikes.

## 7. Validation Checks
```python
# Sharpe ratio must monotonically non-increase as capital increases
sharpes = [t.sharpe_ratio for t in capacity_report.tiers]
assert all(x >= y for x, y in zip(sharpes, sharpes[1:])), "Sharpe ratio did not decay with scaling capital!"
```

## 8. Production Checklist
- [ ] Determine capacity threshold where Sharpe ratio falls below 1.0.
- [ ] Incorporate asset borrow availability limits for short strategies.
