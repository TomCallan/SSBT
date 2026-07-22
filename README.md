# SSBT — Super Simple Backtesting Tool

Minimal, performant, event-driven backtester in Python. Vectorised indicator computation via Polars/NumPy, sequential event-driven execution for market realism. Built for high-speed initial strategy testing.

## Features

- **Event-driven core** — sequential bar/tick processing, realistic order matching, portfolio tracking
- **Vectorised precompute** — indicators computed once on full DataFrame, event loop indexes signals
- **Parameter sweeps** — grid search across strategy params, data loaded once and reused
- **Walk-forward optimisation** — rolling or expanding IS/OS windows
- **Full order types** — MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP
- **Time-in-force** — GTC, GTD, IOC, FOK, DAY
- **OCO orders** — one-cancels-other linkage
- **Pre-allocated equity curve** — NumPy arrays, zero per-bar allocations
- **Parquet native** — Polars lazy read, NumPy array caching for fast iteration

## Install

```bash
uv venv .venv
uv pip install -e .
```

Dependencies: `polars`, `numpy`, `matplotlib`.

## Data Preparation

SSBT reads Parquet files. Two formats supported:

### OHLCV Bars

Columns: `timestamp`, `open`, `high`, `low`, `close`, `volume`

```python
import polars as pl

df = pl.DataFrame({
    "timestamp": [1640995200000000000, 1641081600000000000, ...],  # ns epoch
    "open":   [100.0, 101.2, ...],
    "high":   [102.5, 103.0, ...],
    "low":    [99.8, 100.5, ...],
    "close":  [101.2, 102.8, ...],
    "volume": [15000, 12000, ...],
})
df.write_parquet("my_data.parquet")
```

### Bid/Ask Quotes

Columns: `timestamp`, `bid`, `ask`

```python
df = pl.DataFrame({
    "timestamp": [1640995200000000000, ...],
    "bid": [99.8, ...],
    "ask": [100.2, ...],
})
df.write_parquet("quotes.parquet")
```

Column names are case-insensitive. Timestamps must be nanosecond epoch integers.

### Converting existing data

```python
import polars as pl

# From CSV
df = pl.read_csv("candles.csv")
# Ensure timestamp is ns epoch
df = df.with_columns(
    pl.col("datetime").str.to_datetime().dt.timestamp("ns").alias("timestamp")
).drop("datetime")
df.write_parquet("candles.parquet")
```

## Creating a Backtest

### 1. Write a strategy

Subclass `Strategy`, implement `on_bar()` (or `on_bidask()` for quote data). Use `on_init()` for precompute.

```python
from ssbt import Strategy, Bar
from ssbt.core.events import Side

class MyStrategy(Strategy):
    def __init__(self, fast_period: int = 10, slow_period: int = 30, qty: float = 100.0):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.qty = qty
        self._signals = None
        self._bar_index = 0
        self._symbol = None
        self._position = 0.0

    def on_init(self, engine) -> None:
        self._symbol = engine.feed.symbols[0]
        df = self.get_dataframe(engine, self._symbol)

        # Precompute SMAs vectorised via Polars
        df = df.with_columns([
            pl.col("close").rolling_mean(self.fast_period).alias("sma_fast"),
            pl.col("close").rolling_mean(self.slow_period).alias("sma_slow"),
        ])

        fast = df["sma_fast"].to_numpy()
        slow = df["sma_slow"].to_numpy()
        import numpy as np
        signals = np.zeros(len(fast))
        valid = ~(np.isnan(fast) | np.isnan(slow))
        signals[valid] = np.where(fast[valid] > slow[valid], 1.0, -1.0)

        crossovers = np.zeros(len(signals), dtype=bool)
        crossovers[1:] = signals[1:] != signals[:-1]
        self._signals = signals
        self._crossovers = crossovers

    def on_bar(self, bar: Bar, engine) -> None:
        idx = self._bar_index
        self._bar_index += 1

        if idx == 0 or not self._crossovers[idx]:
            return

        if self._signals[idx] > 0 and self._position <= 0:
            if self._position < 0:
                engine.submit_order(self.market_order(self._symbol, Side.BUY, abs(self._position)))
                self._position = 0
            engine.submit_order(self.market_order(self._symbol, Side.BUY, self.qty))
            self._position += self.qty
        elif self._signals[idx] < 0 and self._position >= 0:
            if self._position > 0:
                engine.submit_order(self.market_order(self._symbol, Side.SELL, self._position))
                self._position = 0
            engine.submit_order(self.market_order(self._symbol, Side.SELL, self.qty))
            self._position -= self.qty

    def on_finish(self, engine) -> None:
        if self._position > 0:
            engine.submit_order(self.market_order(self._symbol, Side.SELL, self._position))
        elif self._position < 0:
            engine.submit_order(self.market_order(self._symbol, Side.BUY, abs(self._position)))
```

### 2. Run the backtest

```python
from ssbt import ParquetFeed, Engine

feed = ParquetFeed("my_data.parquet", symbol="BTCUSDT")
strategy = MyStrategy(fast_period=10, slow_period=30, qty=100.0)
engine = Engine(feed, strategy, initial_cash=100_000.0)

result = engine.run()
```

### 3. Use advanced order types

```python
from ssbt import Strategy
from ssbt.core.events import Side, TimeInForce

class AdvancedStrategy(Strategy):
    def on_bar(self, bar, engine):
        # Limit order with IOC
        engine.submit_order(self.limit_order(
            "BTCUSDT", Side.BUY, qty=1.0, price=99000.0,
            tif=TimeInForce.IOC,
        ))

        # Stop-limit order
        engine.submit_order(self.stop_limit_order(
            "BTCUSDT", Side.BUY, qty=1.0,
            stop_price=105000.0, limit_price=105500.0,
        ))

        # Trailing stop (2% offset)
        engine.submit_order(self.trailing_stop_order(
            "BTCUSDT", Side.SELL, qty=1.0,
            trail_offset=0.02, is_pct=True,
        ))

        # OCO: take profit + stop loss
        tp = self.limit_order("BTCUSDT", Side.SELL, 1.0, 110000.0)
        sl = self.stop_order("BTCUSDT", Side.SELL, 1.0, 95000.0)
        engine.submit_oco(*self.oco_order(tp, sl))
```

## Outputs

### Metrics

```python
from ssbt import compute_metrics, format_metrics

metrics = compute_metrics(result.equity_curve, result.trades)
print(format_metrics(metrics))
```

Available metrics:

| Metric | Description |
|---|---|
| `total_return` | Total return percentage |
| `sharpe` | Annualised Sharpe ratio |
| `sortino` | Annualised Sortino ratio |
| `calmar` | Calmar ratio (annual return / max drawdown) |
| `max_drawdown` | Maximum drawdown percentage |
| `n_trades` | Number of round-trip trades |
| `win_rate` | Fraction of winning trades |
| `profit_factor` | Gross profit / gross loss |
| `avg_trade` | Average PnL per trade (net of commission) |
| `final_equity` | Final portfolio equity |
| `n_periods` | Number of bars/events processed |

### Equity curve

```python
equity = result.equity_curve  # NumPy array, shape (n, 2): [timestamp, equity]
```

### Trade log

```python
for trade in result.trades:
    print(f"{trade.symbol} entry={trade.entry_price} exit={trade.exit_price} "
          f"pnl={trade.pnl} qty={trade.qty}")
```

### Fills

```python
for fill in result.fills:
    print(f"{fill.side} {fill.qty} @ {fill.price} commission={fill.commission}")
```

### Plots

```python
from ssbt.analytics.plots import plot_equity_curve, plot_drawdown, plot_trades

plot_equity_curve(result.equity_curve, save_path="equity.png")
plot_drawdown(result.equity_curve, save_path="drawdown.png")
plot_trades(result.equity_curve, result.trades, save_path="trades.png")
```

### Export to CSV

```python
import polars as pl

# Trade log
pl.DataFrame({
    "symbol": [t.symbol for t in result.trades],
    "entry_time": [t.entry_time for t in result.trades],
    "exit_time": [t.exit_time for t in result.trades],
    "entry_price": [t.entry_price for t in result.trades],
    "exit_price": [t.exit_price for t in result.trades],
    "pnl": [t.pnl for t in result.trades],
}).write_csv("trades.csv")
```

## Parameter Sweeps

```python
from ssbt import param_grid, run_sweep, ParquetFeed

feed = ParquetFeed("data.parquet", symbol="BTCUSDT")
combos = param_grid(
    fast_period=[5, 10, 15, 20],
    slow_period=[20, 30, 50, 80],
    qty=[100.0],
)

results = run_sweep(MyStrategy, feed, combos, initial_cash=100_000.0)

# Best result by final equity
best = results[0]
print(f"Best: {best.params} equity={best.final_equity:.0f} sharpe={best.metrics['sharpe']:.3f}")

# Export all results
from ssbt.analytics.sweep import results_to_dataframe
results_to_dataframe(results).write_csv("sweep_results.csv")
```

## Walk-Forward Optimisation

```python
from ssbt import walk_forward, param_grid, ParquetFeed

feed = ParquetFeed("data.parquet", symbol="BTCUSDT")
combos = param_grid(fast_period=[5, 10, 20], slow_period=[20, 30, 50])

wf = walk_forward(
    strategy_class=MyStrategy,
    feed=feed,
    param_grid=combos,
    in_sample_size=1000,
    out_sample_size=500,
    mode="rolling",  # or "expanding"
)

print(f"Avg OS Sharpe: {wf.avg_os_sharpe:.4f}")
print(f"Avg OS Return: {wf.avg_os_return*100:.2f}%")

# Export
wf.to_dataframe().write_csv("walkforward.csv")
```

## Run Examples

```bash
# Single backtest with synthetic data
python -m ssbt.examples.sma_cross

# Parameter sweep + walk-forward
python -m ssbt.examples.sweep_example
```

## API Reference

### Core classes

| Class | Purpose |
|---|---|
| `Engine(feed, strategy, initial_cash)` | Runs the backtest |
| `ParquetFeed(path, symbol)` | Reads Parquet, yields events |
| `InMemoryFeed(df, symbol, start, end)` | Pre-loaded DataFrame, fastest for sweeps |
| `MatchingEngine(slippage_fn, commission_fn)` | Order matching with configurable models |
| `Portfolio(initial_cash, n_bars)` | Tracks positions, cash, equity, trades |
| `Strategy` | ABC — subclass to implement your strategy |

### Order helpers (on `Strategy`)

| Method | Order type |
|---|---|
| `market_order(symbol, side, qty, tif)` | MARKET |
| `limit_order(symbol, side, qty, price, tif)` | LIMIT |
| `stop_order(symbol, side, qty, price, tif)` | STOP / STOP_MARKET |
| `stop_limit_order(symbol, side, qty, stop_price, limit_price, tif)` | STOP_LIMIT |
| `trailing_stop_order(symbol, side, qty, trail_offset, is_pct, tif)` | TRAILING_STOP |
| `oco_order(order_a, order_b)` | OCO pair (submit via `engine.submit_oco()`) |

### Engine methods

| Method | Purpose |
|---|---|
| `engine.run()` | Execute backtest, returns `BacktestResult` |
| `engine.submit_order(order)` | Submit single order |
| `engine.submit_oco(order_a, order_b)` | Submit OCO pair |
| `engine.cancel_order(order_id)` | Cancel pending order |
| `engine.cancel_all(symbol)` | Cancel all pending orders for symbol |

### Enums

```python
from ssbt.core.events import Side, OrderType, OrderStatus, TimeInForce

Side.BUY, Side.SELL
OrderType.MARKET, LIMIT, STOP, STOP_LIMIT, STOP_MARKET, TRAILING_STOP
OrderStatus.PENDING, FILLED, CANCELLED, PARTIALLY_FILLED, EXPIRED
TimeInForce.GTC, GTD, IOC, FOK, DAY
```

## Project Structure

```
ssbt/
├── core/
│   ├── events.py        # Event + order types, enums
│   ├── engine.py        # Event loop (fast path + generic)
│   ├── matching.py      # Order matching (all types, TIF, OCO)
│   └── portfolio.py     # Positions, equity curve, trade tracking
├── data/
│   └── feed.py          # ParquetFeed + InMemoryFeed
├── strategy/
│   └── base.py          # Strategy ABC + order helpers
├── analytics/
│   ├── metrics.py       # Sharpe, Sortino, Calmar, DD, win rate, PF
│   ├── plots.py         # Equity curve, drawdown, trade markers
│   ├── sweep.py         # Parameter grid search
│   └── walkforward.py   # Walk-forward optimisation
└── examples/
    ├── sma_cross.py     # Single backtest demo
    └── sweep_example.py # Sweep + walk-forward demo
```
