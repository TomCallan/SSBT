# Current Backtest Flow (Pre-Refactoring Baseline)

Documented 2026-07-27. Describes the backtesting engine before exploration engine refactoring.

## Entry Points

- `ssbt.examples.sma_cross` — CLI example: `python -m ssbt.examples.sma_cross`
- `ssbt.examples.multi_symbol` — multi-symbol example
- `ssbt.examples.sweep_example` — parameter sweep example
- `ssbt.analytics.optimization` — `run_sweep()`, `walk_forward()` programmatic API

## Core Engine Flow (`core/engine.py`)

```
Feed (ParquetFeed | InMemoryFeed)
  → Engine.__init__(feed, strategy, initial_cash, matching)
  → Engine.run()
      → strategy.on_init(engine)          # precompute indicators
      → for each bar/bidask event:
          → MatchingEngine.process_bar()   # match pending orders
          → Portfolio.apply_fill()          # update cash/position
          → strategy.on_bar()               # user logic, may submit orders
          → MatchingEngine.process_bar()    # process new orders
          → Portfolio.update_prices()       # mark-to-market, record equity
      → strategy.on_finish(engine)          # close positions
      → BacktestResult
```

### Fast Path (single-symbol)

When feed is `InMemoryFeed` with `dtype == "bar"`:
1. `feed.to_arrays()` extracts raw NumPy arrays
2. Pre-allocated `Bar` object mutated in-place (zero allocation per bar)
3. Direct array indexing for OHLCV fields

### Generic Path (multi-symbol / ParquetFeed)

When feed is multi-symbol `ParquetFeed` or `InMemoryFeed` iterator:
1. Feed yields `Bar` or `BidAsk` objects chronologically
2. `isinstance()` checks per event
3. Per-symbol `Portfolio.update_prices()` with dict lookups

## Multi-Symbol Engine (`core/multi_engine.py`)

```
MultiSymbolEngine.__init__(feeds: dict[str, Feed], strategy, allocation_fn, ...)
  → Convert all feeds to InMemoryFeed
  → MultiSymbolEngine.run()
      → Merge all symbol arrays by timestamp
      → Strategy.on_init()
      → For each (timestamp, symbol, bar_index) in sorted order:
          → MatchingEngine.process_bar() for that symbol
          → Strategy.on_bar() for that symbol
          → Portfolio.update_prices() for that symbol
          → On rebalance boundary: allocation_fn() → Portfolio.rebalance()
      → Final rebalance
      → BacktestResult
```

## Data Layer (`data/feed.py`)

- `InMemoryFeed`: wraps a `pl.DataFrame`, caches `to_arrays()` as `{col: np.ndarray}`
  - `to_arrays()`: returns all columns as NumPy arrays (fast path)
  - `__iter__()`: yields `Bar` or `BidAsk` objects (generic path)
- `ParquetFeed`: reads from parquet files
  - Single symbol: yields bars via `InMemoryFeed`
  - Multi symbol: merges by timestamp, yields interleaved events
  - `to_inmemory()`: converts to `InMemoryFeed` for fast path

## Matching Engine (`core/matching.py`)

Supports: MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP orders
Supports: GTC, GTD, IOC, FOK, DAY time-in-force
Supports: OCO pairs
Default: 1 bps slippage, 1 bps commission

## Portfolio (`core/portfolio.py`)

- Tracks cash, positions per symbol, equity curve
- Equity = cash + Σ(position * last_price)
- Pre-allocated `(n, 2)` NumPy array for equity curve
- Round-trip trade tracking (FIFO matching)

## Analytics (`analytics/metrics.py`)

Pure NumPy computations:
- Sharpe, Sortino, Calmar ratios
- Max drawdown, win rate, profit factor
- Average trade PnL

## Vectorised Backtester (`core/vectorised.py`)

JIT-compiled (numba) batch backtest for parameter sweeps:
- Single sweep: `_vectorised_backtest_kernel`
- Matrix sweep: `_matrix_sweep_kernel` (parallel)
- Single-symbol only, signal-array input

## Known-Good Baseline Metrics

Captured from `SmaCrossStrategy(10, 30, qty=100.0)` on 5000-bar synthetic OHLCV (seed=42), `initial_cash=100_000`:

| Metric         | Value       |
|----------------|-------------|
| final_equity   | 95231.27    |
| total_return   | -4.77%      |
| sharpe         | -0.12       |
| sortino        | -0.18       |
| calmar         | -0.29       |
| max_drawdown   | -16.44%     |
| n_trades       | 166         |
| win_rate       | 43.37%      |
| profit_factor  | 0.89        |
| avg_trade      | -28.63      |

## Key Dependencies

- Python >= 3.10
- polars >= 0.20 (DataFrame operations, parquet I/O)
- numpy >= 1.24 (arrays, vectorised math)
- matplotlib >= 3.7 (charts)
- numba >= 0.58 (optional, for vectorised backtester JIT)
