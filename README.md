# SSBT — High-Performance Quantitative Exploration & Backtesting Engine

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Performance](https://img.shields.io/badge/engine-Polars%20%7C%20Numba%20%7C%20Zero--Allocation-green.svg)]()
[![Audit Status](https://img.shields.io/badge/audit-Anti--Lookahead%20Verified-brightgreen.svg)]()

SSBT is an ultra-fast, event-driven quantitative backtesting, market exploration, and statistical analysis platform engineered for quantitative researchers, algorithmic traders, and prop challenge developers. Built on top of Polars, Arrow memory, NumPy, and Numba C-kernels, SSBT delivers high-speed backtesting (>1,000,000 bars/sec) with strict anti-lookahead causality auditing, market microstructure execution realism, statistical overfitting defense (DSR/PBO), deterministic reproducibility, and real-time streaming IPC for live interfaces.

This master README provides a comprehensive, self-contained reference covering every module, API, execution assumption, and quantitative feature in the SSBT repository.

---

## Table of Contents

1. [Data Ingestion Architecture & Philosophy](#1-data-ingestion-architecture--philosophy)
2. [Core Execution Engine & Matching Mechanics](#2-core-execution-engine--matching-mechanics)
3. [Strategy Development API & Order Types](#3-strategy-development-api--order-types)
4. [Market Microstructure & Orderbook Engine](#4-market-microstructure--orderbook-engine)
5. [Point-in-Time Data Integrity & Multi-Timeframe Alignment](#5-point-in-time-data-integrity--multi-timeframe-alignment)
6. [Statistical Overfitting Defense (DSR, PBO, Monte Carlo)](#6-statistical-overfitting-defense-dsr-pbo-monte-carlo)
7. [Portfolio Risk Budgeting & Capacity Overlays](#7-portfolio-risk-budgeting--capacity-overlays)
8. [Immutable Reproducibility & Rerun Verification CLI](#8-immutable-reproducibility--rerun-verification-cli)
9. [Causal Audit Logging & Assumptions Reporting](#9-causal-audit-logging--assumptions-reporting)
10. [Generic Event Exploration Engine & Specs](#10-generic-event-exploration-engine--specs)
11. [Real-Time IPC Execution Streaming](#11-real-time-ipc-execution-streaming)
12. [Interactive GUIs (Desktop Studio & Web Dashboard)](#12-interactive-guis-desktop-studio--web-dashboard)
13. [Prop Challenge Compliance Evaluation](#13-prop-challenge-compliance-evaluation)
14. [Testing, Verification & Due-Diligence Commands](#14-testing-verification--due-diligence-commands)
15. [Repository Layout](#15-repository-layout)

---

## 1. Data Ingestion Architecture & Philosophy

> **Zero Internal Data Dependencies**: SSBT harnesses zero internal data downloading APIs. All market data (CSV, Parquet, CCXT, SQL, yfinance, or custom data vendor feeds) must be ingested externally by the user and provided as Polars DataFrames into `ssbt.data.feed.InMemoryFeed` or `ParquetFeed`.

### Standard Data Schema
Every Polars DataFrame supplied to SSBT requires the following schema:

| Column | Type | Description |
| :--- | :--- | :--- |
| `timestamp` | `Int64` | Monotonic nanosecond or millisecond Unix epoch timestamp |
| `symbol` | `Utf8` | Ticker symbol string (e.g. `"GC=F"`, `"BTC/USD"`, `"AAPL"`) |
| `open` | `Float64` | Opening bar price |
| `high` | `Float64` | Highest bar price |
| `low` | `Float64` | Lowest bar price |
| `close` | `Float64` | Closing bar price |
| `volume` | `Float64` | Bar trading volume |

### Code Example: Creating Feeds

```python
import polars as pl
from ssbt.data.feed import InMemoryFeed, ParquetFeed

# Option A: Ingest Polars DataFrame into InMemoryFeed
df = pl.DataFrame({
    "timestamp": [1700000000000, 1700000060000, 1700000120000],
    "symbol": ["GC=F"] * 3,
    "open": [2000.0, 2002.0, 2001.0],
    "high": [2005.0, 2004.0, 2006.0],
    "low": [1998.0, 2000.0, 1999.0],
    "close": [2002.0, 2001.0, 2005.0],
    "volume": [1500.0, 1200.0, 1800.0],
})
feed = InMemoryFeed(df, symbol="GC=F")

# Option B: Load directly from disk via ParquetFeed
feed_parquet = ParquetFeed("data/gold_1m.parquet", symbol="GC=F")
```

---

## 2. Core Execution Engine & Matching Mechanics

SSBT's core engine (`Engine` and `MatchingEngine`) evaluates strategy orders against incoming market bars or bid/ask quotes using single-pass Numba-accelerated event loops.

### Worst-Case Adverse Execution Rule ("Fills Against Position Then For")
To eliminate backtest optimism, pending orders matching on the same bar's price range are evaluated in strict conservative priority:
1. **Priority 0 (Adverse Exit Orders)**: Stop Loss, Stop Market, and Trailing Stop orders evaluate FIRST to ensure open positions trigger stop-loss exits before favorable price moves occur.
2. **Priority 1 (Limit Orders)**: Profit-taking limit orders and stop-limit entries evaluate SECOND.
3. **Priority 2 (Market Orders)**: Market orders execute at next open.

### Code Example: Launching Engine

```python
from ssbt.core.engine import Engine
from ssbt.data.feed import InMemoryFeed

feed = InMemoryFeed(df, symbol="GC=F")
strategy = MyStrategy()
engine = Engine(feed, strategy, initial_cash=10000.0)
result = engine.run()

print(f"Final Equity: ${result.final_equity:,.2f} | Total Trades: {len(result.trades)}")
```

---

## 3. Strategy Development API & Order Types

Strategies inherit from `ssbt.Strategy` and implement lifecycle methods:
- `on_init(engine)`: Called before bar processing starts.
- `on_bar(bar, engine)`: Called on every incoming bar.
- `on_finish(engine)`: Called after bar processing finishes.

### Position State Helpers
- `self.is_flat(engine, symbol)`: Returns `True` if no position exists for `symbol`.
- `self.get_position_qty(engine, symbol)`: Returns signed float position size (`+long`, `-short`, `0.0 flat`).

### Supported Order Types & Time-in-Force (TIF)
- **Market**: `self.market_order(symbol, side, qty)`
- **Limit**: `self.limit_order(symbol, side, qty, price)`
- **Stop**: `self.stop_order(symbol, side, qty, stop_price)`
- **Stop-Limit**: `Order(..., type=OrderType.STOP_LIMIT, price=stop_price, stop_limit_price=limit_price)`
- **Trailing Stop**: `Order(..., type=OrderType.TRAILING_STOP, trail_offset=offset_val, trail_is_pct=False)`
- **OCO (One-Cancels-the-Other)**: `engine.submit_oco(order_a, order_b)`
- **Time-in-Force**: `TimeInForce.GTC`, `TimeInForce.GTD` (`expire_at=ts`), `TimeInForce.IOC`, `TimeInForce.FOK`, `TimeInForce.DAY`.

### Complete Strategy Code Example

```python
import numpy as np
from ssbt import Strategy, Side, Order, OrderType, OrderStatus, Bar

class ProductionQuantStrategy(Strategy):
    def __init__(self, risk_dollars: float = 85.0):
        super().__init__()
        self.risk_dollars = risk_dollars
        self.closes = []
        self.highs = []
        self.lows = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)

        if len(self.closes) < 22:
            return

        ema = float(np.mean(self.closes[-20:]))
        diffs = np.diff(self.closes[-15:])
        gains = np.where(diffs > 0, diffs, 0.0)
        losses = np.where(diffs < 0, -diffs, 0.0)
        rsi = 100.0 - (100.0 / (1.0 + (np.mean(gains) / (np.mean(losses) + 1e-8))))

        atr = float(np.mean(np.maximum(
            np.array(self.highs[-10:]) - np.array(self.lows[-10:]),
            np.abs(np.array(self.highs[-10:]) - np.array(self.closes[-11:-1]))
        )))

        # Entry logic: Only enter when FLAT
        if bar.close > ema and 45.0 <= rsi <= 65.0 and self.is_flat(engine, bar.symbol):
            stop_dist = max(1.8 * atr, bar.close * 0.008)
            qty = round(self.risk_dollars / stop_dist, 2)

            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty))
            engine.submit_order(Order(
                id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
            ))
```

---

## 4. Market Microstructure & Orderbook Engine

SSBT includes advanced market microstructure execution models and synthetic orderbook reconstruction.

### Microstructure Execution Models (`ssbt.execution.models`)
- `ImpactModel`: Square-root market impact ($\text{Impact} = \text{Price} \cdot \gamma \cdot \sigma \cdot \sqrt{\text{Qty}/\text{ADV}}$).
- `LiquidityCapModel`: Restricts max execution per bar to $\le 10\%$ ADV, marking orders as `OrderStatus.PARTIALLY_FILLED`.
- `BorrowCostModel`: Calculates short position annualized borrow fee financing.
- `RealisticExecutionEngine`: Combined execution wrapper.

### Arbitrary-Resolution Synthetic L2 Orderbook Reconstruction (`ssbt.data.orderbook`)
Takes data of **any base resolution $x$** (e.g. 1d, 4h, 1h, 15m) and synthesizes multi-level L2 bid/ask depth quotes at **target resolution $y$** (e.g. 1m sub-bar ticks) using `OrderBookEngine.reconstruct(df, sub_bar_splits=N)`.

```python
import polars as pl
from ssbt import OrderBookEngine

# Base Data x: 1-hour bars
data_1h = pl.DataFrame({
    "timestamp": [1700000000000, 1700003600000],
    "symbol": ["GC=F", "GC=F"],
    "open": [2000.0, 2005.0],
    "high": [2010.0, 2012.0],
    "low": [1995.0, 2002.0],
    "close": [2005.0, 2008.0],
    "volume": [10000.0, 12000.0],
})

# Synthesize Target Sub-Bar Resolution y (60 1-minute orderbook ticks per hour)
quotes_1m = OrderBookEngine.reconstruct(
    data_1h,
    sub_bar_splits=60,
    spread_pct=0.0002,
    depth_levels=5,
)

# Convert to Polars DataFrame
orderbook_df = OrderBookEngine.to_dataframe(quotes_1m)
print(f"Reconstructed {len(quotes_1m)} L2 quotes from {len(data_1h)} bars.")
```

Run orderbook example:
```bash
uv run python examples/orderbook_reconstruction_example.py
```

---

## 5. Point-in-Time Data Integrity & Multi-Timeframe Alignment

To prevent forward-looking feature leakage across multi-timeframe joins (e.g. joining 1d indicators to 1h bars), `ssbt.data.point_in_time` provides asynchronous point-in-time join tools.

```python
from ssbt import align_multi_timeframe, validate_point_in_time_join

# Asynchronously join 1d indicator features to 1h bars using completed prior bars only
joined_df = align_multi_timeframe(lower_tf_df=df_1h, higher_tf_df=df_1d, time_col="timestamp")

# Assert zero lookahead leakage (throws CausalityViolationError if violated)
validate_point_in_time_join(joined_df, time_col="timestamp")
```

---

## 6. Statistical Overfitting Defense (DSR, PBO, Monte Carlo)

SSBT incorporates statistical safeguards (`ssbt.analytics.robustness`) to evaluate parameter sweep data-snooping risk:

1. **Deflated Sharpe Ratio (DSR)**: Adjusts observed Sharpe ratio for trial counts ($N$), trial variance, skewness, and kurtosis (Bailey & Lopez de Prado).
2. **Probability of Backtest Overfitting (PBO)**: Resamples return matrices to evaluate in-sample vs out-of-sample rank degradation.
3. **Monte Carlo Resampling**: Bootstraps 1,000 trade sequence permutations to compute non-parametric 95% confidence bounds.

```python
from ssbt import deflated_sharpe_ratio, probability_of_backtest_overfitting, monte_carlo_trade_permutation

# 1. Deflated Sharpe Ratio
dsr = deflated_sharpe_ratio(observed_sharpe=2.22, var_sharpes=0.25, n_trials=10, returns_len=252)
print(f"DSR Statistical Confidence: {dsr*100:.1f}%")

# 2. Monte Carlo 1,000 Trade Resampling
mc_res = monte_carlo_trade_permutation(trade_pnls=[50.0, -20.0, 100.0, -30.0], initial_cash=5000.0, n_iterations=1000)
print(f"95% CI Lower Equity: ${mc_res['ci_95_lower']:,.2f} | 95th Max DD: {mc_res['max_dd_95']*100:.2f}%")
```

---

## 7. Portfolio Risk Budgeting & Capacity Overlays

Incorporate portfolio overlays (`ssbt.portfolio.risk`):
- `VolatilityTargetingOverlay`: Dynamically scales position sizes to target constant annualized portfolio volatility (e.g. 12% target vol).
- `StrategyCapacityAnalyzer`: Estimates maximum strategy AUM capacity before market impact reduces Sharpe below threshold.

```python
from ssbt import VolatilityTargetingOverlay, StrategyCapacityAnalyzer

# Volatility targeting
vol_overlay = VolatilityTargetingOverlay(target_volatility=0.12, lookback=20)
scale = vol_overlay.get_scaling_factor(recent_returns)

# AUM capacity estimation
analyzer = StrategyCapacityAnalyzer(target_min_sharpe=1.0)
max_aum = analyzer.estimate_capacity(base_sharpe=2.22, annual_adv_dollars=350_000_000.0)
print(f"Estimated Max Strategy AUM Capacity: ${max_aum:,.2f}")
```

---

## 8. Immutable Reproducibility & Rerun Verification CLI

Every backtest automatically generates `environment_snapshot.json` in `artifacts/<run_id>/` capturing Git commit SHA, branch, Python environment, platform, random seed, and config SHA-256 hash.

### Verification CLI
Re-run any historical backtest with 0.00% variance:

```bash
uv run python -m ssbt.cli.rerun artifacts/inst_run_20260728_211537
```

Output:
```
+-------------------------------------------------------------+
| SSBT DETERMINISTIC RERUN VERIFIER                           |
| Artifact Path: artifacts/inst_run_20260728_211537          |
+-------------------------------------------------------------+
Git Commit SHA: a6badcb
Git Branch: dev-generic-exploration-engine-plan
Random Seed: 42
Original Integrity SHA-256: ce7182998be87a57...

[PASS] Deterministic Rerun Verified! Equity Curve & Trade Lineage 100% Identical.
```

---

## 9. Causal Audit Logging & Assumptions Reporting

`AuditLogger` verifies fill timestamp causality and emits two formal audit files to `artifacts/<run_id>/`:
1. `audit_trail.json`: Detailed execution lineage records and SHA-256 integrity hash.
2. `simulation_assumptions_report.json`: Formal execution realism report detailing fill rules, market impact parameters, point-in-time checks, and reproducibility hashes.

```python
from ssbt import AuditLogger, BacktestAdapter

adapter = BacktestAdapter(initial_cash=5000.0)
res = adapter.run_backtest(feed, strategy)

logger = AuditLogger(verbose=True)
report = logger.generate_report(backtest_result=res["raw_result"], output_dir="artifacts/run_01")
print(f"Audit Passed: {report.is_valid} | SHA-256: {report.integrity_hash}")
```

---

## 10. Generic Event Exploration Engine & Specs

SSBT includes a YAML-driven market exploration engine (`ssbt.experiments.runner`) for event study research:

```python
from ssbt import load_experiment, run_experiment

spec = load_experiment("ssbt/experiments/examples/volume_spike.yaml")
result = run_experiment("ssbt/experiments/examples/volume_spike.yaml")
print(f"Events Detected: {result.events.height} | Forward Returns Computed: {result.outcomes.height}")
```

---

## 11. Real-Time IPC Execution Streaming

`ExecutionStreamPublisher` streams tick-by-tick `BAR`, `ORDER`, `FILL`, `TRADE`, and `EQUITY` events over sockets or JSONL files (`artifacts/<run_id>/execution_stream.jsonl`) for live GUI dashboards.

```python
from ssbt import ExecutionStreamPublisher, StreamEvent

publisher = ExecutionStreamPublisher(log_path="artifacts/run_01/execution_stream.jsonl")
publisher.subscribe(lambda event: print(f"Live Event: {event.event_type} at {event.timestamp}"))
publisher.publish("FILL", 1700000000000, {"symbol": "GC=F", "qty": 1.0, "price": 2000.0})
```

---

## 12. Interactive GUIs (Desktop Studio & Web Dashboard)

SSBT includes zero-dependency interactive GUIs in `gui_examples/`:

### Interactive Tkinter Desktop Studio
```bash
uv run python gui_examples/desktop_gui.py
```
Features control toolbars, live Canvas equity curve rendering, metric cards, and real-time execution log feeds.

### HTML5 Web Dashboard (Browser)
```bash
uv run python gui_examples/web_gui.py
```
Launches an HTTP API server on `http://localhost:8080` with browser control panels and interactive HTML5 Canvas equity curve charts.

---

## 13. Prop Challenge Compliance Evaluation

SSBT evaluates strategies against strict institutional prop firm challenge rules (e.g., Velotrade $5k Account Challenge):
- **Starting Capital**: $5,000.00
- **Profit Target**: +$400.00 (+8.0%)
- **Max Daily Drawdown**: -$250.00 (-5.0%)
- **Max Total Drawdown**: -$500.00 (-10.0%)

Run the multi-ticker timeframe prop matrix suite:
```bash
uv run python examples/multi_ticker_timeframe_suite.py
```

---

## 14. Testing, Verification & Due-Diligence Commands

Run full pytest suite (148 unit, property invariant, and scale benchmark tests):
```bash
uv run python -m pytest ssbt/tests/ -v
```

Run institutional due-diligence suite:
```bash
uv run python examples/institutional_due_diligence_suite.py
```

Run synthetic L2 orderbook reconstruction example:
```bash
uv run python examples/orderbook_reconstruction_example.py
```

Run deterministic rerun CLI verifier:
```bash
uv run python -m ssbt.cli.rerun artifacts/inst_run_20260728_211537
```

---

## 15. Repository Layout

```
SSBT/
├── ssbt/                         # Core SSBT Quantitative Package
│   ├── core/                     # Engine, Portfolio, Matching (Worst-case & Partial Fills), Events
│   ├── data/                     # InMemory, Parquet, Point-In-Time Alignment, Orderbook Depth
│   ├── strategy/                 # Strategy Base Class & Position Helpers
│   ├── analytics/                # AuditLogger, Metrics, Stream Publisher, Robustness, Terminal
│   ├── execution/                # ImpactModel, LiquidityCap, BorrowCost Engine
│   ├── portfolio/                # VolatilityTargeting, Strategy Capacity Analyzer
│   ├── experiments/              # Exploration Engine, Spec Parser, Reproducibility & Charting
│   └── cli/                      # Command Line Utilities (ssbt.cli.rerun)
├── gui_examples/                 # Real-time Interactive GUIs
│   ├── desktop_gui.py            # Tkinter Desktop Quantitative Studio
│   └── web_gui.py                # Web Browser Dashboard & HTTP API Server
├── strategies_vault/             # Proprietary Strategy Vault (Gitignored)
│   └── triple_confluence.py      # Production Triple Confluence Strategy
├── examples/                     # Ready-to-Run Research & Due-Diligence Suites
│   ├── orderbook_reconstruction_example.py
│   ├── institutional_due_diligence_suite.py
│   ├── multi_ticker_timeframe_suite.py
│   ├── velotrade_5k_challenge.py
│   └── triple_confluence_detail.py
├── docs/                         # Quantitative Documentation & Architecture
│   ├── INSTITUTIONAL_DUE_DILIGENCE.md
│   ├── ASSUMPTIONS_AND_LIMITATIONS.md
│   └── HOW_TO_TRUST_RESULTS.md
├── artifacts/                    # Run Artifacts, Charts & Audit Trails (Gitignored)
├── pyproject.toml                # Package configuration (Python 3.12+)
└── README.md                     # Master Quantitative Guide & Technical Reference
```

---

## License
MIT License. Engineered for quantitative trading, systematic strategy exploration, and prop challenge evaluation.
