# SSBT: Quantitative Strategy Exploration Engine & Backtester

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**SSBT** is an event-driven quantitative strategy exploration, backtesting, and institutional verification engine written in Python. It is designed for quantitative researchers, algorithmic traders, and strategy developers who require point-in-time anti-lookahead causality auditing, worst-case market microstructure execution realism, statistical overfitting defenses, and 100% deterministic rerun reproducibility.

---

## Technical Features & Architectural Controls

- **Universal Dynamic Tick Stream**: Merges L1 Raw Trade Ticks, L2/L3 Orderbook depth quotes, and OHLCV bars of any resolution (1d, 4h, 1h, 15m, 5m, 1m) into a unified, forward-filled tick stream (`UniversalTickStream`).
- **Worst-Case Adverse Execution Model**: Evaluates pending limit, stop, and trailing stop orders in adverse fill sequence ("fills against position then for"), prioritizing stop-loss evaluation prior to profit targets on same-bar triggers.
- **Microstructure Realism**: Reconstructs synthetic L2 depth quotes (`rebuild_orderbook_from_bars`), supports partial fills (`OrderStatus.PARTIALLY_FILLED`), ADV market impact (`ImpactModel`), volume participation caps (`LiquidityCapModel`), and short borrow cost financing (`BorrowCostModel`).
- **Statistical Overfitting Defense Suite**: Calculates Deflated Sharpe Ratio (`deflated_sharpe_ratio`), Probability of Backtest Overfitting (`probability_of_backtest_overfitting`), and 1,000-iteration Monte Carlo trade sequence permutations.
- **Anti-Lookahead Causality Audit**: `AuditLogger` verifies timestamp causality, validates point-in-time joins (`align_multi_timeframe`), and emits SHA-256 integrity signatures alongside `simulation_assumptions_report.json`.
- **Immutable Reproducibility & Rerun Verification**: Captures environment snapshots (`environment_snapshot.json`) and verifies 100% deterministic rerun fidelity via `uv run python -m ssbt.cli.rerun <run_id>`.
- **Universal 1-Line Plotting API**: Instant rendering of multi-asset equity curves, underwater drawdowns, trade PnLs, and statistical robustness audits via `ssbt.plot()` and `@ssbt.autoplot`.
- **Real-Time IPC Streaming**: Emits live `BAR`, `ORDER`, `FILL`, `TRADE`, and `EQUITY` events via `ExecutionStreamPublisher` over sockets or JSONL logs for Tkinter Desktop & Web Dashboard GUIs.
- **High-Throughput Performance**: Leverages Polars Apache Arrow memory and pre-allocated Numba bar loops for backtesting execution throughput exceeding 1,000,000 bars/second.

---

## Architectural Data Flow

```
[ External Market Data ] ---> [ Polars DataFrame ]
                                     |
                                     v
                       [ UniversalTickStream ] (Forward-Filling)
                                     |
                                     v
                           [ Engine Core ] <---> [ Strategy ]
                                     |
                          (Adverse Priority Matching)
                                     |
                                     v
             +-----------------------+-----------------------+
             |                       |                       |
             v                       v                       v
    [ AuditLogger ]        [ Overfitting Suite ]   [ ExecutionStreamPublisher ]
   (Point-in-Time Join)    (DSR / PBO / Monte Carlo) (Real-Time IPC Streaming)
             |                       |                       |
             v                       v                       v
   [ audit_trail.json ]    [ robustness_audit.png ]   [ Desktop / Web GUI ]
```

---

## Installation & Environment Setup

SSBT requires Python 3.10+ and uses `uv` for fast dependency resolution.

```bash
# Clone the repository
git clone https://github.com/TomCallan/SSBT.git
cd SSBT

# Install dependencies via uv
uv sync
```

---

## Quickstart (10-Minute Path to First Backtest)

Here is a complete, minimal example running a moving-average crossover strategy over Polars market data:

```python
import polars as pl
from ssbt import Strategy, Side, Bar, InMemoryFeed, BacktestAdapter, plot

# 1. Define Strategy Logic
class MovingAverageCross(Strategy):
    def __init__(self, fast: int = 10, slow: int = 30):
        super().__init__()
        self.fast = fast
        self.slow = slow
        self.closes = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        if len(self.closes) < self.slow:
            return

        fast_ma = sum(self.closes[-self.fast:]) / self.fast
        slow_ma = sum(self.closes[-self.slow:]) / self.slow

        if fast_ma > slow_ma and self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty=1.0))
        elif fast_ma < slow_ma and not self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, qty=1.0))

# 2. Supply External Polars DataFrame
df = pl.DataFrame({
    "timestamp": [1000, 2000, 3000, 4000, 5000],
    "symbol": ["BTC"] * 5,
    "open": [100.0, 102.0, 105.0, 103.0, 108.0],
    "high": [103.0, 106.0, 107.0, 105.0, 110.0],
    "low": [99.0, 101.0, 104.0, 102.0, 107.0],
    "close": [102.0, 105.0, 103.0, 108.0, 112.0],
    "volume": [10.0, 15.0, 12.0, 18.0, 20.0],
})

# 3. Execute Backtest
feed = InMemoryFeed(df, symbol="BTC")
adapter = BacktestAdapter(initial_cash=10000.0)
result = adapter.run_backtest(feed, MovingAverageCross())

# 4. Plot Performance Dashboard (Saved to artifacts/latest/strategy_dashboard.png)
plot(result, title="Moving Average Cross Performance")
```

---

## Strategy API & Position Helpers

Inherit from `ssbt.Strategy` and override `on_bar(bar, engine)`:

```python
from ssbt import Strategy, Side, Order, OrderType, OrderStatus, Bar

class MyStrategy(Strategy):
    def on_bar(self, bar: Bar, engine) -> None:
        # Check current position status
        if self.is_flat(engine, bar.symbol):
            qty = self.get_position_qty(engine, bar.symbol)
            
            # Submit market order
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty=1.0))
            
            # Submit trailing stop order
            engine.submit_order(Order(
                id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                qty=1.0, trail_offset=5.0, status=OrderStatus.PENDING
            ))
```

---

## Data Model & External Data Ingestion Philosophy

SSBT embraces zero internal data downloading APIs. All market data is passed into the engine as Polars DataFrames using `InMemoryFeed` or `ParquetFeed`.

### Schema Requirement
| Column | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | `Int64` | Unix Epoch timestamp (milliseconds or nanoseconds, strictly monotonic) |
| `symbol` | `Utf8` | Asset ticker symbol |
| `open` | `Float64` | Bar open price |
| `high` | `Float64` | Bar high price |
| `low` | `Float64` | Bar low price |
| `close` | `Float64` | Bar close price |
| `volume` | `Float64` | Bar volume |

---

## Universal Tick Stream Engine (`UniversalTickStream`)

Unify raw ticks, L2/L3 orderbook depth quotes, and multi-timeframe OHLCV bars into a single, chronologically sorted, forward-filled tick stream:

```python
from ssbt.data.universal_tick import UniversalTickStream, UniversalTickFeed
from ssbt import MatchingEngine

# Merge Raw Ticks, L2 Depth Quotes, and 1-Hour OHLCV Bars
stream_ticks = UniversalTickStream.build_stream(
    data_sources=[data_ticks, data_l2_quotes, data_1h_bars],
    symbol="GC=F",
    spread_pct=0.0002,
    forward_fill=True,  # Forward-fills bid/ask/mid state across interval gaps
)

feed = UniversalTickFeed(stream_ticks)
matching = MatchingEngine()

while feed.has_next():
    tick = feed.next_tick()
    fills = matching.process_tick(tick)
```

Run universal tick stream example:
```bash
uv run python examples/universal_tick_stream_example.py
```

---

## Market Microstructure Realism & Adverse Execution

SSBT enforces conservative market microstructure matching rules:

1. **Adverse Match Order**: On intrabar price movements, pending orders match in worst-case adverse priority (evaluating stop-loss triggers before profit target fills).
2. **Partial Fills**: Fills respects orderbook volume depth (`OrderStatus.PARTIALLY_FILLED`).
3. **ADV Market Impact**: `ImpactModel(gamma=0.5)` models square-root price impact based on trade volume vs Average Daily Volume.
4. **Liquidity Cap**: `LiquidityCapModel(max_adv_pct=0.10)` restricts execution volume to a max percentage of bar volume.
5. **Short Borrow Cost**: `BorrowCostModel(annual_borrow_rate=0.01)` calculates daily short position financing costs.

---

## Statistical Overfitting Defense Suite (DSR, PBO, Monte Carlo)

Defend your strategy against data mining bias and backtest overfitting:

```python
from ssbt import deflated_sharpe_ratio, probability_of_backtest_overfitting, monte_carlo_trade_permutation

# 1. Deflated Sharpe Ratio (DSR)
dsr_score = deflated_sharpe_ratio(
    observed_sharpe=2.14,
    var_sharpes=0.20,
    n_trials=10,
    returns_len=252,
)

# 2. Probability of Backtest Overfitting (PBO)
pbo_score = probability_of_backtest_overfitting(returns_matrix)

# 3. Monte Carlo 1,000-Iteration Resampling Audit
mc_results = monte_carlo_trade_permutation(
    trade_pnls=trade_pnls,
    initial_cash=5000.0,
    n_iterations=1000,
)
```

---

## Anti-Lookahead Causality & Point-In-Time Integrity (`AuditLogger`)

Validate timestamp causality and emit SHA-256 signed audit trails:

```python
from ssbt import AuditLogger

logger = AuditLogger(verbose=False)
report = logger.generate_report(backtest_result=result["raw_result"], output_dir="artifacts/run_01")

print(f"Audit Passed: {report.is_valid}")
print(f"Integrity Checksum SHA-256: {report.integrity_hash}")
```

---

## Immutable Reproducibility & Rerun Verification

Capture environment snapshots (`environment_snapshot.json`) capturing Git commit SHA, branch, Python environment, platform, random seed, and config hash.

Verify 100% deterministic rerun fidelity:
```bash
uv run python -m ssbt.cli.rerun artifacts/run_20260729_154929
```

---

## Universal 1-Line Visual Plotting API (`ssbt.plot` & `@ssbt.autoplot`)

Plot any backtest result, Polars/Pandas DataFrame, or numpy series instantly:

```python
import ssbt

# Option A: 1-line backtest result plotting (Renders 3-panel strategy dashboard)
result = adapter.run_backtest(feed, strategy)
ssbt.plot(result, title="Strategy Performance Dashboard")

# Option B: Dedicated Statistical Robustness Plot
ssbt.plot_robustness_dashboard(dsr_val=0.98, pbo_val=0.04, mc_res=mc_results)

# Option C: @autoplot decorator on any data/strategy function
@ssbt.autoplot
def run_my_strategy():
    return adapter.run_backtest(feed, strategy)
```

### Supported Autoplotter Data Types
| Data Structure | Automatically Generated Plot Type | Output Details |
| :--- | :--- | :--- |
| **Backtest Adapter Dict / `BacktestResult`** | **`strategy_dashboard.png`** | 1. Multi-Asset Equity Curves ($) vs Capital Baseline<br>2. Multi-Asset Underwater Drawdown Area Fill (%)<br>3. Per-Trade PnL Sequence ($) |
| **Statistical Overfitting Metrics** | **`robustness_audit.png`** | 1. DSR % & PBO % Visual Gauges<br>2. Monte Carlo 1,000 Resampling 95% CI Equity Band |
| **Polars / Pandas DataFrame** | **Price / Quote / Feature Chart** | - OHLCV tables (`close` column): Renders price line chart<br>- Quote tables (`bid`, `ask` columns): Renders bid/ask spread lines |

---

## Artifact Output Directory Hierarchy

Every backtest execution writes all 13 institutional run artifacts directly to `artifacts/run_<timestamp>/` and mirrors them **1-to-1** into `artifacts/latest/`:

```
artifacts/
├── latest/                          # Directory: 100% exact 1-to-1 mirror of active run folder
└── run_20260729_154929/              # Directory: Isolated timestamped run folder
    ├── audit_trail.json             # 1. Anti-lookahead timestamp causality audit report
    ├── environment_snapshot.json    # 2. Immutable reproducibility snapshot
    ├── execution_stream.jsonl       # 3. Real-time IPC stream log of engine execution events
    ├── matrix_equity.png            # 4. Multi-equity comparison chart
    ├── matrix_results.csv           # 5. Tabular summary across all ticker/timeframe matrix combinations
    ├── metrics_overview.json        # 6. Detailed metrics overview dictionary
    ├── overfitting_defense_audit.json # 7. DSR, PBO, and Monte Carlo audit JSON
    ├── performance_metrics.png      # 8. Dedicated Sharpe, Return %, and Drawdown bar chart comparison
    ├── robustness_audit.png         # 9. Dedicated DSR %, PBO %, and Monte Carlo 95% CI plot chart
    ├── simulation_assumptions_report.json # 10. Realism assumptions audit report
    ├── strategy_dashboard.png       # 11. Clean 3-panel Multi-Asset Strategy Performance Dashboard
    ├── trade_log.csv                # 12. Itemized trade execution log (CSV)
    └── trade_log.parquet            # 13. Itemized trade execution log (Parquet)
```

---

## Real-Time IPC Event Streaming & Live Data Ingestion

Stream engine bar events, order submissions, fills, trades, and portfolio equity updates in real-time to high-throughput buffered file sinks, sockets, ring buffers, or custom callbacks:

```python
from ssbt import ExecutionStreamPublisher, BufferedFileSink, SocketIPCSink

# High-throughput buffered IPC file stream
publisher = ExecutionStreamPublisher(sinks=[
    BufferedFileSink("artifacts/latest/execution_stream.jsonl", batch_size=500),
    SocketIPCSink(host="127.0.0.1", port=9999)
])
```

SSBT supports real-time, live market data ingestion from external WebSocket listeners, REST API pollers, ZeroMQ streams, or gRPC connectors using `LiveStreamFeed`. External connectors push live bars, bid/ask quotes, or trade ticks directly into SSBT's real-time engine loop:

```python
from ssbt import Engine, LiveStreamFeed, QueueOverflowPolicy

# 1. Initialize thread-safe live stream feed
feed = LiveStreamFeed(
    symbols="BTCUSD",
    max_queue_size=100_000,
    overflow_policy=QueueOverflowPolicy.DISCARD_OLDEST,
)

# 2. In your external WebSocket/REST client callback thread:
def on_websocket_quote(data):
    feed.push_bidask(
        timestamp=data["timestamp"],
        symbol=data["symbol"],
        bid=data["bid"],
        ask=data["ask"],
    )

# 3. Execute strategy against live incoming market events
engine = Engine(feed=feed, strategy=my_live_strategy)
result = engine.run()
```

---

## Testing & Verification Suite

Run the full pytest suite (155 unit & integration tests):

```bash
uv run python -m pytest ssbt/tests/ -v
```

---

## Performance Notes & Benchmarks

- **Throughput**: >1,000,000 bars/second execution throughput on single-threaded core loop.
- **Memory Footprint**: Leverages Apache Arrow in-memory zero-copy Polars structures.

---

## Public API Reference

```python
from ssbt import (
    # Core Strategy & Engine
    Strategy, Side, Order, OrderType, OrderStatus, Bar, Engine, MultiSymbolEngine,
    
    # Data & Feeds
    InMemoryFeed, ParquetFeed, UniversalTickStream, UniversalTickFeed,
    align_multi_timeframe, validate_point_in_time_join,
    
    # Backtesting & Adapters
    BacktestAdapter,
    
    # Microstructure Realism
    ImpactModel, LiquidityCapModel, BorrowCostModel, RealisticExecutionEngine,
    
    # Risk & Capacity
    VolatilityTargetingOverlay, StrategyCapacityAnalyzer,
    
    # Overfitting Defenses
    deflated_sharpe_ratio, probability_of_backtest_overfitting, monte_carlo_trade_permutation,
    
    # Audit & Reproducibility
    AuditLogger, capture_environment_snapshot, sync_latest_run_folder, ExecutionStreamPublisher,
    
    # Plotting & Dashboard API
    plot, autoplot, plot_strategy_dashboard, plot_robustness_dashboard, plot_performance_metrics,
    
    # Exception Hierarchy
    SSBTError, DataError, ExecutionError, AuditError,
)
```

---

## License & Disclaimer

This project is licensed under the MIT License. SSBT is a quantitative research and backtesting framework intended strictly for educational and empirical analysis purposes. It does not constitute financial advice or investment recommendations.
