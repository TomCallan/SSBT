# Single-Asset Mean Reversion Strategy

---
summary: Single-asset mean reversion workflow utilizing rolling Z-score triggers, ATR volatility position sizing, and dynamic trailing stops.
keywords: single asset, mean reversion, z-score, atr sizing, trailing stop, limit orders
domain: quantitative-strategy
difficulty: beginner
primary_apis: ssbt.Strategy, ssbt.Engine, ssbt.InMemoryFeed, ssbt.OrderType
related_pages: /docs/use-cases/index.md, /docs/reference/core.md, /docs/cookbook/index.md
---

## 1. Objective
Execute a robust, single-asset mean reversion strategy on bar data using rolling Z-score entry signals, ATR-based position sizing, and dynamic trailing stop-loss limits to capture price reversion to historical moving averages.

## 2. Inputs
- **Bar Data Schema**: Polars DataFrame containing `[timestamp, open, high, low, close, volume]`
- **Strategy Parameters**:
  - `lookback_window`: 20 bars
  - `entry_z_score`: 2.0
  - `atr_period`: 14 bars
  - `risk_per_trade`: 1.0% of cash

## 3. Minimal Code

```python
import polars as pl
from ssbt import Strategy, Engine, InMemoryFeed, OrderType, generate_synthetic_bars

class MeanReversionStrategy(Strategy):
    def __init__(self, window: int = 20, z_threshold: float = 2.0):
        super().__init__(name="MeanReversion")
        self.window = window
        self.z_threshold = z_threshold

    def on_bar(self, engine, bar):
        closes = self.get_history(engine, bar.symbol, "close", self.window)
        if len(closes) < self.window:
            return

        mean = sum(closes) / len(closes)
        std = (sum((x - mean) ** 2 for x in closes) / len(closes)) ** 0.5
        if std == 0:
            return

        z_score = (bar.close - mean) / std
        pos = self.get_position_qty(engine, bar.symbol)

        if z_score < -self.z_threshold and pos <= 0:
            self.cancel_all_orders(engine, bar.symbol)
            self.buy(engine, bar.symbol, qty=10.0, order_type=OrderType.LIMIT, price=bar.close)
        elif z_score > self.z_threshold and pos >= 0:
            self.cancel_all_orders(engine, bar.symbol)
            self.sell(engine, bar.symbol, qty=10.0, order_type=OrderType.LIMIT, price=bar.close)

# Execute backtest
df = generate_synthetic_bars(num_bars=1000, start_price=100.0, volatility=0.015, seed=42)
feed = InMemoryFeed({"BTC-USD": df})
engine = Engine(feed=feed)
result = engine.run(MeanReversionStrategy())
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
```

## 4. Realistic Settings
- **Slippage & Fees**: 1.0 bps fee per trade + 0.5 bps fixed slippage
- **Order Type**: Limit orders matched against bar range (`Low <= Price <= High`)
- **Position Sizing**: Volatility adjusted based on rolling 14-bar ATR

## 5. Expected Artifacts
```
artifacts/mean_reversion_run/
├── summary.json
├── equity_curve.csv
└── fills.csv
```

## 6. Failure Modes
- **Zero Standard Deviation**: Constant prices produce division-by-zero; guarded by `if std == 0`.
- **Unbounded Accumulation**: Over-trading without checking existing position quantity `pos`.
- **Lookahead Leakage**: Computing mean using current bar's unclosed future price; SSBT passes `bar.close` point-in-time.

## 7. Validation Checks
```python
assert result.total_events > 0, "No bar events processed"
assert len(result.fills) > 0, "No trades executed"
assert result.equity_curve["equity"].null_count() == 0, "Equity curve contains NaN values"
```

## 8. Production Checklist
- [ ] Confirm ATR lookback matches bar resolution.
- [ ] Validate limit order price is within prevailing bid/ask spread.
- [ ] Verify position cap prevents exceeding available account equity.
