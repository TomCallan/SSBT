# Task-Oriented Cookbook Snippets

---
summary: Task-oriented recipe snippets for common SSBT implementation tasks.
keywords: cookbook, snippets, borrow costs, liquidity caps, batch sweeps, timestamp leakage, gui streaming
domain: quantitative-engineering
difficulty: intermediate
primary_apis: ssbt.execution, ssbt.optimization, ssbt.analytics
related_pages: /docs/index.md, /docs/reference/index.md, /docs/use-cases/index.md
---

## 1. How to Model Short Borrow Costs

```python
from ssbt.execution import BorrowCostModel, RealisticExecutionEngine

# 2% annual borrow cost
borrow_model = BorrowCostModel(annual_rate=0.02)
exec_engine = RealisticExecutionEngine(borrow_model=borrow_model)
```

## 2. How to Enforce Liquidity Participation Caps

```python
from ssbt.execution import LiquidityCapModel, RealisticExecutionEngine

# Cap order fills at 5% of bar volume
liquidity_model = LiquidityCapModel(max_participation=0.05)
exec_engine = RealisticExecutionEngine(liquidity_model=liquidity_model)
```

## 3. How to Run Batch Strategy Sweeps Reproducibly

```python
from ssbt.optimization import run_sweep, ParamRange, IntParam

param_grid = {"window": IntParam(10, 50, step=10)}
results = run_sweep(strategy_cls=MyStrategy, feed=feed, param_grid=param_grid, seed=42)
```

## 4. How to Debug Timestamp Leakage

```python
from ssbt.data import validate_point_in_time_join

# Raises ValueError if slow_timestamp > fast_timestamp
validate_point_in_time_join(df, fast_time_col="timestamp", slow_time_col="timestamp_slow")
```

## 5. How to Stream Events into GUI

```python
from ssbt.analytics import ExecutionStreamPublisher, SocketIPCSink

sink = SocketIPCSink(host="127.0.0.1", port=9099)
publisher = ExecutionStreamPublisher(sinks=[sink])
```
