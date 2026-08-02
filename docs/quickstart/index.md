# Quickstart Guide

---
summary: Quickstart guide covering 5-minute, 15-minute, and 30-minute SSBT backtesting workflows.
keywords: quickstart, minimal backtest, realistic execution, audit, deflated sharpe ratio, determinism
domain: quantitative-finance
difficulty: beginner
primary_apis: ssbt.quick_backtest, ssbt.Engine, ssbt.InMemoryFeed, ssbt.execution.RealisticExecutionEngine
related_pages: /docs/index.md, /docs/use-cases/index.md, /docs/architecture/index.md
---

Welcome to the SSBT Quickstart. Choose your run depth based on available time and objective.

- [5-Minute Run: Minimal Backtest](#5-minute-run-minimal-backtest)
- [15-Minute Realistic Run: Market Microstructure & Partial Fills](#15-minute-realistic-run-market-microstructure--partial-fills)
- [30-Minute Full Stack: Audit, DSR/PBO, Rerun & Reporting](#30-minute-full-stack-audit-dsrpbo-rerun--reporting)

---

## 5-Minute Run: Minimal Backtest

Run a simple moving average crossover backtest using `InMemoryFeed` and `@strategy`.

```python
import polars as pl
from ssbt import quick_backtest, strategy, generate_synthetic_bars, OrderType

# Generate test bar data
df = generate_synthetic_bars(num_bars=1000, start_price=100.0, volatility=0.01, seed=42)

@strategy(name="Minimal_SMA_Cross")
def sma_cross(self, engine, bar):
    closes = self.get_history(engine, bar.symbol, "close", 20)
    if len(closes) < 20:
        return

    sma5 = sum(closes[-5:]) / 5.0
    sma20 = sum(closes[-20:]) / 20.0
    pos_qty = self.get_position_qty(engine, bar.symbol)

    if sma5 > sma20 and pos_qty <= 0:
        self.buy(engine, bar.symbol, qty=10.0, order_type=OrderType.MARKET)
    elif sma5 < sma20 and pos_qty > 0:
        self.sell(engine, bar.symbol, qty=10.0, order_type=OrderType.MARKET)

result = quick_backtest(df, sma_cross, initial_cash=100_000.0)
print(result.summary())
```

---

## 15-Minute Realistic Run: Market Microstructure & Partial Fills

Add square-root market impact, liquidity participation caps, short borrow costs, and synthetic orderbook partial fills.

```python
from ssbt import Engine, InMemoryFeed, Strategy, OrderType
from ssbt.execution import RealisticExecutionEngine, ImpactModel, LiquidityCapModel, BorrowCostModel
from ssbt.data import rebuild_orderbook_from_bars, OrderBookFeed
from ssbt.quick import generate_synthetic_bars

df = generate_synthetic_bars(num_bars=5000, start_price=50.0, volatility=0.02, seed=42)
feed = InMemoryFeed({"BTC-USD": df})

# Enable microstructure execution engine
exec_engine = RealisticExecutionEngine(
    impact_model=ImpactModel(eta=0.1),
    liquidity_model=LiquidityCapModel(max_participation=0.05), # 5% ADV cap
    borrow_model=BorrowCostModel(annual_rate=0.02)             # 2% short borrow cost
)

class RealisticStrategy(Strategy):
    def on_bar(self, engine, bar):
        pos = self.get_position_qty(engine, bar.symbol)
        if pos == 0:
            self.buy(engine, bar.symbol, qty=50.0, order_type=OrderType.MARKET)

engine = Engine(feed=feed, execution_engine=exec_engine)
result = engine.run(RealisticStrategy())
print(f"Total Return: {result.total_return:.2%}")
print(f"Fills Executed: {len(result.fills)}")
```

---

## 30-Minute Full Stack: Audit, DSR/PBO, Rerun & Reporting

Execute audit logging, evaluate overfitting statistical defenses, verify 100% deterministic rerun integrity, and export complete audit artifacts.

```python
from ssbt import Engine, InMemoryFeed, AuditLogger, deflated_sharpe_ratio, probability_of_backtest_overfitting
from ssbt.quick import generate_synthetic_bars, sma_cross

df = generate_synthetic_bars(num_bars=10000, start_price=100.0, volatility=0.015, seed=123)
feed = InMemoryFeed({"ETH-USD": df})

# Attach Audit Logger for point-in-time causality verification
audit_logger = AuditLogger(enabled=True)
engine = Engine(feed=feed, audit_logger=audit_logger)

result = engine.run(sma_cross)

# Calculate Overfitting Defense Metrics
returns = result.equity_curve.select(pl.col("equity").pct_change()).drop_nulls()["equity"].to_numpy()
dsr_val, p_val = deflated_sharpe_ratio(returns, num_trials=50, track_record_length=len(returns))
pbo_val = probability_of_backtest_overfitting(returns, num_slices=10)

print(f"Deflated Sharpe Ratio: {dsr_val:.4f} (p-value: {p_val:.4f})")
print(f"Probability of Backtest Overfitting (PBO): {pbo_val:.2%}")

# Export Audit Signature & Snapshot
artifact_dir = audit_logger.export_artifacts(output_dir="artifacts/quickstart_run")
print(f"Run exported to: {artifact_dir}")
```

To verify deterministic rerun from CLI:
```bash
uv run python -m ssbt.cli.rerun artifacts/quickstart_run
```
