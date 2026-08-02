# Microstructure Models API Reference (`ssbt.execution`)

---
summary: API reference for market impact, liquidity participation caps, short borrow costs, and queue priority models.
keywords: reference, microstructure, ImpactModel, LiquidityCapModel, BorrowCostModel
domain: api-reference
difficulty: advanced
primary_apis: ssbt.execution.ImpactModel, ssbt.execution.LiquidityCapModel, ssbt.execution.BorrowCostModel
related_pages: /docs/index.md, /docs/reference/index.md, /docs/use-cases/capacity-and-impact-study.md
---

## `ssbt.execution.ImpactModel`

Square-root ADV market impact model: $ \Delta P = \eta \cdot \sigma \sqrt{Q / ADV} $.

```python
class ImpactModel:
    def __init__(self, eta: float = 0.1, gamma: float = 0.5)
```

## `ssbt.execution.LiquidityCapModel`

Enforces maximum volume participation cap per bar.

```python
class LiquidityCapModel:
    def __init__(self, max_participation: float = 0.05) # 5% ADV cap
```

## `ssbt.execution.BorrowCostModel`

Calculates annualized short position borrowing fees.

```python
class BorrowCostModel:
    def __init__(self, annual_rate: float = 0.01) # 1.0% annual borrow rate
```
