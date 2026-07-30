# SSBT

Fast, event-driven backtesting for traders who write Python.

You bring your data. You write your strategy. SSBT runs it against realistic market conditions and tells you if the numbers hold up.

No config files. No YAML. No JSON DSL. Just Python.

---

## Install

```bash
git clone https://github.com/TomCallan/SSBT.git
cd SSBT
uv sync
```

Requires Python 3.10+ and [uv](https://github.com/astral-sh/uv).

---

## The simplest possible backtest

```python
import ssbt

data = ssbt.generate_synthetic_bars(n_bars=1000, seed=42)

@ssbt.strategy
def my_strat(bar, engine):
    if bar.close > bar.open:
        engine.submit_order(ssbt.Strategy.market_order(bar.symbol, ssbt.Side.BUY, 1.0))

result = ssbt.quick_backtest(my_strat, data, symbol="BTC-USD", verbose=True)
print(result)
# <QuickResult symbol='BTC-USD' events=1000 return=+4.21% sharpe=1.34 max_dd=-3.10%>
```

---

## Writing strategies

### As a function

```python
@ssbt.strategy
def breakout(bar, engine):
    if bar.close > bar.high * 1.002:
        engine.submit_order(ssbt.Strategy.market_order(bar.symbol, ssbt.Side.BUY, 1.0))
```

### As a class

Use a class when you need to keep state between bars (moving averages, counters, etc):

```python
from ssbt import Strategy, Side, Bar

class SmaCross(Strategy):
    def __init__(self, fast: int = 10, slow: int = 30):
        self.fast = fast
        self.slow = slow
        self._closes: list[float] = []

    def on_bar(self, bar: Bar, engine) -> None:
        self._closes.append(bar.close)
        if len(self._closes) < self.slow:
            return

        fast_ma = sum(self._closes[-self.fast:]) / self.fast
        slow_ma = sum(self._closes[-self.slow:]) / self.slow

        if fast_ma > slow_ma and self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, 1.0))
        elif fast_ma < slow_ma and not self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, 1.0))
```

Pass the class or an instance — both work:

```python
result = ssbt.quick_backtest(SmaCross(fast=10, slow=30), data, symbol="ES=F")
result = ssbt.quick_backtest(SmaCross, data, symbol="ES=F")  # uses defaults
```

---

## Position helpers

```python
def on_bar(self, bar: Bar, engine) -> None:
    if self.is_flat(engine, bar.symbol):
        engine.submit_order(self.market_order(bar.symbol, Side.BUY, 1.0))

    qty = self.get_position_qty(engine, bar.symbol)
    df  = self.get_dataframe(engine, bar.symbol)   # full OHLCV history for this symbol
```

---

## Order types

```python
# Market — fills at next bar open
engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty=1.0))

# Limit — fills when price reaches the level
engine.submit_order(self.limit_order(bar.symbol, Side.BUY, qty=1.0, price=49_500.0))

# Stop — triggers at stop_price, fills at market
engine.submit_order(self.stop_order(bar.symbol, Side.SELL, qty=1.0, price=48_000.0))

# Stop-limit — triggers at stop_price, only fills at limit_price or better
engine.submit_order(self.stop_limit_order(
    bar.symbol, Side.SELL, qty=1.0,
    stop_price=48_000.0, limit_price=47_900.0
))

# Trailing stop — moves with the market, offset in price points
engine.submit_order(self.trailing_stop_order(bar.symbol, Side.SELL, qty=1.0, trail_offset=500.0))
```

---

## Your data

SSBT never downloads anything. You supply data in whatever format you already have:

```python
import polars as pl
import pandas as pd

# Polars DataFrame
result = ssbt.quick_backtest(strategy, pl.read_parquet("data.parquet"), symbol="BTC-USD")

# Pandas DataFrame
result = ssbt.quick_backtest(strategy, pd.read_csv("data.csv"), symbol="BTC-USD")

# File path — Parquet or CSV
result = ssbt.quick_backtest(strategy, "data.parquet", symbol="BTC-USD")

# Dict
result = ssbt.quick_backtest(strategy, {
    "timestamp": [...],  # int ms epoch, or datetime
    "open": [...],
    "high": [...],
    "low": [...],
    "close": [...],
    "volume": [...],
}, symbol="BTC-USD")
```

Required columns: `timestamp`, `open`, `high`, `low`, `close`, `volume`. The `symbol` column is added automatically if missing.

---

## Synthetic data

No data file yet? Generate bars to test strategy logic immediately:

```python
data = ssbt.generate_synthetic_bars(
    n_bars=2000,
    start_price=100.0,
    volatility=0.01,   # daily vol as a fraction
    drift=0.0001,
    seed=42,
)
```

---

## Reading the result

```python
result = ssbt.quick_backtest(strategy, data, symbol="BTC-USD")

result.total_return    # e.g. 0.042
result.sharpe_ratio
result.max_drawdown    # negative, e.g. -0.031
result.n_events        # bars processed
result.fills           # list of Fill objects
result.trades          # list of Trade objects
result.equity_curve    # numpy array

result.to_dict()       # export as dict
result.to_json()       # export as JSON string
result.plot()          # equity curve chart
```

---

## How execution works

SSBT fills orders in the same order that works against you in live markets:

- **Stop-losses before profit targets.** If a bar's range covers both your stop and your target, the stop fills first.
- **Partial fills.** Orders respect volume depth reconstructed from bar data.
- **No lookahead.** The engine processes bars one at a time and validates causality automatically.
- **Bid/ask spread** on entries and exits.
- **Market impact** — large orders degrade fill price based on order size vs average daily volume.

---

## Full engine control

`quick_backtest` is a convenience wrapper. For direct engine control:

```python
from ssbt import BacktestAdapter, InMemoryFeed
import polars as pl

feed = InMemoryFeed(pl.read_parquet("data.parquet"), symbol="BTC-USD")
adapter = BacktestAdapter(initial_cash=100_000.0)
result = adapter.run_backtest(feed, SmaCross(fast=10, slow=30))

print(result["metrics"])
```

---

## Multi-symbol

```python
from ssbt import MultiSymbolEngine, InMemoryFeed

feeds = {
    "BTC-USD": InMemoryFeed(pl.read_parquet("btc.parquet"), symbol="BTC-USD"),
    "ETH-USD": InMemoryFeed(pl.read_parquet("eth.parquet"), symbol="ETH-USD"),
}

engine = MultiSymbolEngine(feeds=feeds, strategy=my_strategy, initial_cash=100_000)
result = engine.run()
```

---

## Parameter sweeps

```python
from ssbt import run_sweep, param_grid

result = run_sweep(
    strategy_cls=SmaCross,
    feed=feed,
    param_grid=param_grid(fast=[5, 10, 20], slow=[30, 50, 100]),
    initial_cash=100_000.0,
)

print(result.to_dataframe().sort("sharpe", descending=True).head(5))
```

## Walk-forward

```python
from ssbt import WalkForwardOptimizer, ParameterSpace, IntParam

space = ParameterSpace([IntParam("fast", 5, 20), IntParam("slow", 30, 100)])

wf = WalkForwardOptimizer(
    strategy_cls=SmaCross,
    param_space=space,
    is_bars=252,
    oos_bars=63,
    initial_cash=100_000.0,
)
wf_result = wf.run(feed)
print(f"OOS Sharpe: {wf_result.overall_oos_sharpe:.2f}  WFE: {wf_result.wfe_ratio:.2f}")
```

---

## Did the strategy just overfit?

If you ran many parameter combinations, check whether the result is real:

```python
from ssbt import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    monte_carlo_trade_permutation,
)

# Is the Sharpe inflated by trying 50 parameter sets?
dsr = deflated_sharpe_ratio(observed_sharpe=2.1, var_sharpes=0.2, n_trials=50, returns_len=252)

# Probability the winner was just luck
pbo = probability_of_backtest_overfitting(returns_matrix)

# How does it look across 1,000 random trade orderings?
mc = monte_carlo_trade_permutation(trade_pnls, initial_cash=100_000, n_iterations=1000)
```

---

## Causality audit

Verify your strategy never used future prices:

```python
from ssbt import AuditLogger

logger = AuditLogger(verbose=True)
report = logger.generate_report(backtest_result=result, output_dir="artifacts/run_01")
print(f"Clean: {report.is_valid}  SHA-256: {report.integrity_hash}")
```

Multi-timeframe data aligned without lookahead:

```python
from ssbt import align_multi_timeframe, validate_point_in_time_join

aligned = align_multi_timeframe(hourly_bars, daily_signals, on="timestamp")
validate_point_in_time_join(aligned)  # raises if future data leaked in
```

---

## Reproducibility

Any run from `BacktestAdapter` records a full environment snapshot — Python version, all package versions, Git SHA, random seed. Rerun it identically:

```bash
uv run python -m ssbt.cli.rerun artifacts/run_20260730_221537
```

The verifier asserts bit-identical results.

---

## Live data

Push bars or quotes from any feed into the engine in real time:

```python
from ssbt import Engine, LiveStreamFeed, QueueOverflowPolicy

feed = LiveStreamFeed(symbols="BTCUSD", max_queue_size=100_000,
                      overflow_policy=QueueOverflowPolicy.DISCARD_OLDEST)

# Call from your WebSocket thread:
feed.push_bar(timestamp=ts, symbol="BTCUSD", open=o, high=h, low=l, close=c, volume=v)
feed.push_bidask(timestamp=ts, symbol="BTCUSD", bid=bid, ask=ask)

engine = Engine(feed=feed, strategy=my_strategy)
engine.run()
```

Stream every engine event to a file or socket:

```python
from ssbt import ExecutionStreamPublisher, BufferedFileSink, SocketIPCSink

publisher = ExecutionStreamPublisher(sinks=[
    BufferedFileSink("stream.jsonl", batch_size=500),
    SocketIPCSink(host="127.0.0.1", port=9999),
])
```

---

## Plotting

```python
result = ssbt.quick_backtest(strategy, data)

result.plot()                                      # equity curve
ssbt.plot(result, title="My Strategy")             # equity, drawdown, per-trade PnL
ssbt.plot_robustness_dashboard(dsr_val=dsr, pbo_val=pbo, mc_res=mc)

@ssbt.autoplot                                     # auto-plot on return
def run():
    return ssbt.quick_backtest(strategy, data)
```

---

## CLI

```bash
ssbt run my_strategy.py data.parquet --symbol BTC-USD --cash 100000
ssbt run my_strategy.py data.parquet --symbol BTC-USD --json    # machine-readable output
ssbt validate my_strategy.py                                    # check for lookahead, missing on_bar
ssbt template sma_cross                                         # print starter template to stdout
```

---

## Artifacts

Each run writes to `artifacts/run_<timestamp>/` and mirrors to `artifacts/latest/`:

```
artifacts/latest/
├── audit_trail.json          causality report + SHA-256
├── environment_snapshot.json git SHA, package versions, seed
├── execution_stream.jsonl    every event the engine emitted
├── strategy_dashboard.png    equity, drawdown, per-trade PnL
├── robustness_audit.png      DSR, PBO, Monte Carlo
├── trade_log.csv
├── trade_log.parquet
└── metrics_overview.json
```

---

## Tests

```bash
uv run python -m pytest ssbt/tests/ -v
```

---

## License

MIT. Not financial advice.
