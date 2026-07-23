# SSBT — Super Simple Backtesting Tool

**Speed first.** SSBT exists because existing Python backtesters force a choice: fast but unrealistic (vectorised only, no proper order types), or realistic but slow (event-driven, no vectorised path). SSBT closes that gap — a Numba-accelerated engine that runs event-driven backtests at 300k+ bars/sec and vectorised backtests at 3.5M+ bars/sec, with full order type realism in both modes. Matrix sweeps pack thousands of parameter combinations into a single Numba kernel call. It's the fastest Python backtester that doesn't sacrifice market realism for speed.

## Features

- **3.5M+ bars/sec vectorised** — Numba JIT, no event loop, market-order strategies
- **300k+ bars/sec event-driven** — full order matching, realistic fills
- **Matrix sweeps** — pack N param combos into one Numba call (vectorbt-style)
- **Extensible optimizer** — `BaseOptimizer` ABC: plug in GA, RL, Bayesian in 15 lines
- **Multi-symbol** — dynamic portfolio allocation via custom callable
- **Full order types** — MARKET, LIMIT, STOP, STOP_LIMIT, STOP_MARKET, TRAILING_STOP
- **Time-in-force** — GTC, GTD, IOC, FOK, DAY
- **OCO orders** — one-cancels-other linkage
- **Walk-forward** — rolling/expanding IS/OS windows, parallel IS sweep
- **Pre-allocated everything** — Bar reuse, NumPy equity, in-place portfolio legs
- **Parquet native** — Polars + NumPy array caching, zero per-bar I/O

## Install

```bash
uv venv .venv
uv pip install -e .
```

Dependencies: `polars`, `numpy`, `numba`, `matplotlib`.

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

## Vectorised Backtest Mode (1M+ bars/sec)

For strategies that only use market orders (SMA cross, RSI, momentum), skip the event loop entirely:

```python
from ssbt import VectorisedStrategy, VectorisedBacktester
import numpy as np
import polars as pl

class SmaVectorised(VectorisedStrategy):
    def __init__(self, fast: int = 10, slow: int = 30, qty: float = 100.0):
        self.fast = fast
        self.slow = slow
        self.qty = qty

    def compute_signals(self, df: pl.DataFrame) -> np.ndarray:
        df = df.with_columns([
            pl.col("close").rolling_mean(self.fast).alias("sma_fast"),
            pl.col("close").rolling_mean(self.slow).alias("sma_slow"),
        ])
        fast = df["sma_fast"].to_numpy()
        slow = df["sma_slow"].to_numpy()
        signals = np.zeros(len(fast))
        valid = ~(np.isnan(fast) | np.isnan(slow))
        signals[valid] = np.where(fast[valid] > slow[valid], 1.0, -1.0)
        return signals

bt = VectorisedBacktester(initial_cash=100_000.0)
result = bt.run(df, SmaVectorised(fast=10, slow=30), symbol="BTC", qty=100.0)
```

The sweep system auto-detects `VectorisedStrategy` subclasses and uses the fast path.

## Multi-Symbol Portfolio with Dynamic Allocation

Backtest across multiple symbols with dynamic portfolio rebalancing via custom allocation callable:

```python
from ssbt import MultiSymbolEngine, ParquetFeed, Strategy
from ssbt.portfolio.allocation import equal_weight, inverse_volatility, custom_allocation

feeds = {
    "BTC": ParquetFeed("btc.parquet", symbol="BTC"),
    "ETH": ParquetFeed("eth.parquet", symbol="ETH"),
    "SOL": ParquetFeed("sol.parquet", symbol="SOL"),
}

# Built-in allocation functions:
# - equal_weight: split capital equally
# - inverse_volatility: equal risk contribution
# - momentum_allocation: weight by recent returns
# - custom_allocation: wrap any callable with context

# Custom allocation function
def my_alloc(bars, timestamp, ctx):
    """Weight by relative strength."""
    # ctx holds any state you passed
    price_history = ctx.get("price_history", {})
    # ... compute weights ...
    return {"BTC": 0.5, "ETH": 0.3, "SOL": 0.2}

alloc_fn = custom_allocation(my_alloc, price_history={})

engine = MultiSymbolEngine(
    feeds=feeds,
    strategy=MyStrategy(),
    allocation_fn=alloc_fn,       # or equal_weight, inverse_volatility(...)
    initial_cash=100_000.0,
    rebalance_freq=5,              # rebalance every 5 bars
)
result = engine.run()
```

## Parameter Sweeps

SSBT offers two sweep modes:

### Standard sweep (one backtest per combo)

```python
from ssbt import param_grid, run_sweep, ParquetFeed

feed = ParquetFeed("data.parquet", symbol="BTCUSDT")
combos = param_grid(fast_period=[5, 10, 15, 20], slow_period=[20, 30, 50, 80], qty=[100.0])

results = run_sweep(MyStrategy, feed, combos, initial_cash=100_000.0)
print(f"Best: {results[0].params} equity={results[0].final_equity:.0f}")
```

### Matrix sweep (all combos in one Numba call)

For `VectorisedStrategy` subclasses, `run_sweep` automatically uses the matrix sweep: all N param combos are packed into a single `(N, n_bars)` signal matrix and processed in one Numba kernel call with `prange` parallelism. Thousands of combos in seconds.

```python
from ssbt import run_matrix_sweep

# 64 combos → one Numba call, not 64 separate backtests
results = run_matrix_sweep(SmaVectorised, df, "BTC", combos, initial_cash=100_000.0)
```

### Extensible Optimizer Interface

Plug in any optimization algorithm — genetic algorithms, reinforcement learning, Bayesian optimization — in ~15 lines. The only contract is `evaluate(params) -> SweepResult`.

```python
from ssbt import BaseOptimizer

class GeneticAlgorithm(BaseOptimizer):
    def search(self):
        import random
        population = self._init_population()
        for gen in range(50):
            fitness = [self.evaluate(p).final_equity for p in population]
            population = self._evolve(population, fitness)
        return self.results

# Usage:
ga = GeneticAlgorithm(MyStrategy, df, "BTC",
    param_space={"fast": [5, 10, 20], "slow": [20, 30, 50]},
    population_size=100)
results = ga.search()
print(f"Best: {ga.best.params} equity={ga.best.final_equity:.0f}")
```

RL works the same way — your agent calls `self.evaluate(params)` and uses the result as reward.

Built-in: `GridSearch` (wraps `run_matrix_sweep` for vectorised, `_run_single` for event-driven).

## Walk-Forward Optimisation

```python
from ssbt import walk_forward, param_grid, ParquetFeed

feed = ParquetFeed("data.parquet", symbol="BTCUSDT")
combos = param_grid(fast_period=[5, 10, 20], slow_period=[20, 30, 50])

wf = walk_forward(MyStrategy, feed, combos, in_sample_size=1000, out_sample_size=500, mode="rolling")
print(f"Avg OS Sharpe: {wf.avg_os_sharpe:.4f}")
wf.to_dataframe().write_csv("walkforward.csv")
```

## Run Examples

```bash
# Single backtest with synthetic data
python -m ssbt.examples.sma_cross

# Parameter sweep + walk-forward
python -m ssbt.examples.sweep_example

# Vectorised vs event-driven benchmark (1M+ bars/sec)
python -m ssbt.examples.vectorised_benchmark

# Multi-symbol portfolio with dynamic allocation
python -m ssbt.examples.multi_symbol
```

## API Reference

### Core classes

| Class | Purpose |
|---|---|
| `Engine(feed, strategy, initial_cash)` | Event-driven backtest engine |
| `MultiSymbolEngine(feeds, strategy, allocation_fn, ...)` | Multi-symbol with dynamic allocation |
| `VectorisedBacktester(initial_cash, commission_bps, slippage_bps)` | No-event-loop vectorised backtest |
| `ParquetFeed(path, symbol)` | Reads Parquet, yields events |
| `InMemoryFeed(df, symbol, start, end)` | Pre-loaded DataFrame, fastest for sweeps |
| `MatchingEngine(slippage_fn, commission_fn)` | Order matching with configurable models |
| `Portfolio(initial_cash, n_bars)` | Tracks positions, cash, equity, trades |
| `Strategy` | ABC — subclass for event-driven strategies |
| `VectorisedStrategy` | ABC — subclass for vectorised strategies (implement `compute_signals`) |

### Order helpers (on `Strategy`)

| Method | Order type |
|---|---|
| `market_order(symbol, side, qty, tif)` | MARKET |
| `limit_order(symbol, side, qty, price, tif)` | LIMIT |
| `stop_order(symbol, side, qty, price, tif)` | STOP / STOP_MARKET |
| `stop_limit_order(symbol, side, qty, stop_price, limit_price, tif)` | STOP_LIMIT |
| `trailing_stop_order(symbol, side, qty, trail_offset, is_pct, tif)` | TRAILING_STOP |

### Engine methods

| Method | Purpose |
|---|---|
| `engine.run()` | Execute backtest, returns `BacktestResult` |
| `engine.submit_order(order)` | Submit single order |
| `engine.submit_oco(order_a, order_b)` | Submit OCO pair |
| `engine.cancel_order(order_id)` | Cancel pending order |
| `engine.cancel_all(symbol)` | Cancel all pending orders for symbol |

### Optimization classes

| Class | Purpose |
|---|---|
| `BaseOptimizer(strategy_class, df, symbol, param_space)` | ABC for custom optimizers (GA, RL, Bayesian) |
| `GridSearch(strategy_class, df, symbol, param_space)` | Built-in grid search (uses matrix sweep for vectorised) |
| `run_matrix_sweep(strategy_class, df, symbol, combos)` | All combos in one Numba call |
| `run_sweep(strategy_class, feed, combos)` | One backtest per combo (auto-detects vectorised) |
| `walk_forward(strategy_class, feed, combos, ...)` | Walk-forward IS/OS optimization |
| `param_grid(**kwargs)` | Generate cartesian product of param lists |

### Project Structure

```
ssbt/
├── core/
│   ├── events.py            # Event + order types, enums, TIF
│   ├── engine.py            # Event loop (Bar reuse, fast path + generic)
│   ├── matching.py          # Order matching (all types, TIF, OCO)
│   ├── portfolio.py         # Positions, equity, trade tracking, rebalance
│   ├── vectorised.py        # VectorisedBacktester + VectorisedStrategy ABC
│   ├── multi_engine.py      # Multi-symbol engine with allocation
│   └── _numba_kernels.py    # Numba JIT kernels (vectorised + matrix sweep)
├── data/
│   └── feed.py              # ParquetFeed + InMemoryFeed
├── strategy/
│   └── base.py              # Strategy ABC + order helpers
├── portfolio/
│   └── allocation.py        # AllocationFn, equal_weight, inverse_vol, custom
├── analytics/
│   ├── optimization.py      # Sweep, matrix sweep, walk-forward, BaseOptimizer
│   ├── metrics.py           # Sharpe, Sortino, Calmar, DD, win rate, PF
│   └── plots.py             # Equity curve, drawdown
└── examples/
    ├── sma_cross.py             # Single backtest demo
    ├── sweep_example.py         # Sweep + walk-forward demo
    ├── vectorised_benchmark.py  # Vectorised vs event-driven speed comparison
    └── multi_symbol.py          # Multi-symbol portfolio with dynamic allocation
```
