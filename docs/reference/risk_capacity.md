# Risk & Capacity API Reference (`ssbt.portfolio`)

---
summary: API reference for volatility targeting overlays, position sizing, risk controls, and strategy capacity analyzers.
keywords: reference, risk, capacity, VolatilityTargetingOverlay, StrategyCapacityAnalyzer
domain: api-reference
difficulty: advanced
primary_apis: ssbt.portfolio.VolatilityTargetingOverlay, ssbt.portfolio.StrategyCapacityAnalyzer
related_pages: /docs/index.md, /docs/reference/index.md, /docs/use-cases/capacity-and-impact-study.md
---

## `ssbt.portfolio.StrategyCapacityAnalyzer`

Evaluates Sharpe ratio degradation and AUM ceilings under market impact models.

```python
class StrategyCapacityAnalyzer:
    def __init__(
        self,
        capital_tiers: List[float],
        impact_model: ImpactModel = None,
        liquidity_model: LiquidityCapModel = None,
        borrow_model: BorrowCostModel = None
    )
```

### Methods
- `run_study(feed: BaseFeed, strategy: Strategy) -> CapacityReport`

---

## `ssbt.portfolio.VolatilityTargetingOverlay`

Scales position leverage dynamically to maintain constant portfolio volatility target.

```python
class VolatilityTargetingOverlay:
    def __init__(self, target_volatility: float = 0.15, lookback_bars: int = 20)
```
