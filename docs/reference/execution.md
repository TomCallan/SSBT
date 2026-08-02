# Execution Engine API Reference (`ssbt.execution`)

---
summary: API reference for realistic execution engines, conservative matching, order status transitions, and fill generation.
keywords: reference, execution, RealisticExecutionEngine, MatchingEngine, L3MatchingEngine
domain: api-reference
difficulty: advanced
primary_apis: ssbt.execution.RealisticExecutionEngine, ssbt.MatchingEngine, ssbt.L3MatchingEngine
related_pages: /docs/index.md, /docs/reference/index.md, /docs/reference/microstructure.md
---

## `ssbt.execution.RealisticExecutionEngine`

High-fidelity execution simulator combining market impact, participation caps, and borrow costs.

```python
class RealisticExecutionEngine(BaseExecutionEngine):
    def __init__(
        self,
        impact_model: ImpactModel = None,
        liquidity_model: LiquidityCapModel = None,
        borrow_model: BorrowCostModel = None
    )
```

### Methods

#### `process_bar(bar: Bar, pending_orders: List[Order]) -> Tuple[List[Fill], List[Order]]`
Evaluates pending orders against prevailing bar pricing, applying impact penalties and liquidity caps.
- **Worst-Case Matching**: Fills stop losses prior to limit orders.
- **Partial Fills**: Emits `OrderStatus.PARTIALLY_FILLED` if requested quantity exceeds participation caps.
