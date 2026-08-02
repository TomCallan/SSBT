# Market Microstructure Stress Test

---
summary: Stress testing strategies against reconstructed synthetic L2 order book depth and partial fill matching.
keywords: market microstructure, orderbook reconstruction, partial fills, l2 depth, conservative matching
domain: quantitative-execution
difficulty: advanced
primary_apis: ssbt.data.rebuild_orderbook_from_bars, ssbt.data.OrderBookEngine, OrderStatus.PARTIALLY_FILLED
related_pages: /docs/use-cases/index.md, /docs/reference/microstructure.md, /docs/architecture/index.md
---

## 1. Objective
Reconstruct synthetic L2 depth quotes from bar data (`rebuild_orderbook_from_bars`) and evaluate order matching behavior under worst-case adverse execution and partial order fills (`OrderStatus.PARTIALLY_FILLED`).

## 2. Inputs
- `df_bars`: Polars DataFrame with `[timestamp, open, high, low, close, volume]`
- **Depth Parameters**: `num_levels=5`, `tick_size=0.01`, `depth_spread_factor=0.0005`

## 3. Minimal Code

```python
from ssbt import Engine, Strategy, OrderType, OrderStatus, generate_synthetic_bars
from ssbt.data import rebuild_orderbook_from_bars, OrderBookEngine, OrderBookFeed

df = generate_synthetic_bars(num_bars=1000, start_price=100.0, volatility=0.02, seed=42)

# Reconstruct L2 depth orderbook quotes
ob_feed = rebuild_orderbook_from_bars(df, symbol="BTC-USD", levels=5)

class MicrostructureStrategy(Strategy):
    def on_bar(self, engine, bar):
        pos = self.get_position_qty(engine, bar.symbol)
        if pos == 0:
            # Large order exceeding top-of-book depth to trigger partial fills
            self.buy(engine, bar.symbol, qty=500.0, order_type=OrderType.LIMIT, price=bar.close)

    def on_order_status(self, engine, order):
        if order.status == OrderStatus.PARTIALLY_FILLED:
            self.log(f"Partial fill received: {order.filled_qty}/{order.qty}")

engine = Engine(feed=ob_feed, execution_engine=OrderBookEngine())
result = engine.run(MicrostructureStrategy())
print(f"Total Fills: {len(result.fills)}")
```

## 4. Realistic Settings
- **Matching Rule**: Fills against position first (adverse fill sequencing).
- **Depth Cap**: Limits single-bar fill volume to cumulative order book level depth.

## 5. Expected Artifacts
```
artifacts/microstructure_run/
├── orderbook_fills.json
└── depth_snapshot.csv
```

## 6. Failure Modes
- **Insufficient Liquidity**: Order remains `PARTIALLY_FILLED` indefinitely if limit price is out of book depth.
- **Tick Size Misalignment**: Order limit prices not rounded to `tick_size`.

## 7. Validation Checks
```python
partial_fills = [f for f in result.fills if f.status == OrderStatus.PARTIALLY_FILLED]
assert len(result.fills) > 0, "No fills executed during microstructure stress test"
```

## 8. Production Checklist
- [ ] Confirm `tick_size` matches target exchange specification.
- [ ] Verify handling of un-filled residual order quantity on strategy stop.
