# SSBT Exploration & Backtesting Engine — Comprehensive Examples

This document provides complete, practical code examples for all SSBT features tailored for **Quantitative Researchers**, **Systematic Traders**, and **Quant Developers / Risk Managers**.

---

## Table of Contents
1. [For Quantitative Researchers](#1-for-quantitative-researchers)
   - [Example 1.1: Event Study via YAML Config & CLI](#example-11-event-study-via-yaml-config--cli)
   - [Example 1.2: Custom Event Plugin (`BaseEvent`)](#example-12-custom-event-plugin-baseevent)
   - [Example 1.3: Custom Outcome Plugin (`BaseOutcome`) & Multi-Horizon Forward Returns](#example-13-custom-outcome-plugin-baseoutcome--multi-horizon-forward-returns)
   - [Example 1.4: Bootstrap Statistical Confidence Intervals & Diagnostics](#example-14-bootstrap-statistical-confidence-intervals--diagnostics)
   - [Example 1.5: Programmatic Experiment Runner](#example-15-programmatic-experiment-runner)
2. [For Systematic Traders](#2-for-systematic-traders)
   - [Example 2.1: Single-Symbol Strategy with Complex Order Types (Trailing Stop, OCO)](#example-21-single-symbol-strategy-with-complex-order-types-trailing-stop-oco)
   - [Example 2.2: TimeInForce Execution (IOC, FOK, GTD, DAY)](#example-22-timeinforce-execution-ioc-fok-gtd-day)
   - [Example 2.3: Multi-Symbol Portfolio Backtesting with Custom Capital Allocation](#example-23-multi-symbol-portfolio-backtesting-with-custom-capital-allocation)
   - [Example 2.4: Vectorised High-Speed Sweep Mode](#example-24-vectorised-high-speed-sweep-mode)
3. [For Quant Developers & Risk Managers](#3-for-quant-developers--risk-managers)
   - [Example 3.1: BacktestAdapter for Unified Metric Extraction](#example-31-backtestadapter-for-unified-metric-extraction)
   - [Example 3.2: Automated Chart Generation & Artifact Packaging](#example-32-automated-chart-generation--artifact-packaging)
   - [Example 3.3: Manifest Verification & SHA-256 Checksum Audit](#example-33-manifest-verification--sha-256-checksum-audit)

---

## 1. For Quantitative Researchers

### Example 1.1: Event Study via YAML Config & CLI
Test a market hypothesis (e.g. Volume Spikes leading to price reversals) without writing backtest execution code.

Save as `experiments/volume_spike_study.yaml`:
```yaml
version: 1
experiment:
  name: "volume_spike_hypothesis"
  type: event_study
  description: "Evaluate forward returns after high-volume breakouts"

dataset:
  source: "data/synthetic_ohlcv.parquet"
  symbol: "SYNTH"
  timeframe: "1d"

events:
  - name: "volume_spike"
    params:
      window: 20
      multiplier: 2.5
      min_volume: 0
    cooldown_bars: 5
    min_separation_bars: 1

outcomes:
  - name: "forward_return"
    params:
      horizons: [1, 5, 10, 20]

analysis:
  confidence:
    method: "bootstrap"
    iterations: 2000
    ci: 0.95
  statistics:
    include: ["mean", "median", "std", "hit_rate", "quantiles"]
    quantiles: [0.05, 0.25, 0.5, 0.75, 0.95]

reporting:
  output_dir: "artifacts"
  formats: ["csv", "json", "parquet"]
  charts: ["distribution", "grouped_bar", "event_timeline"]
```

Run from CLI:
```bash
ssbt-run experiments/volume_spike_study.yaml
```

---

### Example 1.2: Custom Event Plugin (`BaseEvent`)
Create custom event detection rules and register them with the engine.

```python
import polars as pl
from ssbt.events.base import BaseEvent, check_event_table
from ssbt.experiments.registry import Registry

class RSIOversoldEvent(BaseEvent):
    """Detect RSI oversold condition (< threshold)."""
    name = "rsi_oversold"

    def compute_events(self, df: pl.DataFrame, params: dict) -> pl.DataFrame:
        period = params.get("period", 14)
        threshold = params.get("threshold", 30.0)

        # Polars expression for price changes
        diff = pl.col("close").diff()
        gain = pl.when(diff > 0).then(diff).otherwise(0.0).ewm_mean(span=period)
        loss = pl.when(diff < 0).then(-diff).otherwise(0.0).ewm_mean(span=period)
        rs = gain / (loss + 1e-10)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        df_with_rsi = df.with_columns(rsi.alias("rsi"))
        triggered = df_with_rsi.filter(pl.col("rsi") < threshold)

        if triggered.is_empty():
            return pl.DataFrame(schema={"event_id": pl.Int64, "timestamp": pl.Int64, "symbol": pl.Utf8, "diagnostics": pl.Object})

        events = triggered.select([
            pl.int_range(1, pl.len() + 1).alias("event_id"),
            pl.col("timestamp"),
            pl.col("symbol"),
            pl.struct(pl.col("rsi")).alias("diagnostics"),
        ])
        check_event_table(events)
        return events

# Register the custom event plugin
registry = Registry()
registry.register_event("rsi_oversold", RSIOversoldEvent)
print("Registered Events:", registry.list_events())
```

---

### Example 1.3: Custom Outcome Plugin (`BaseOutcome`) & Multi-Horizon Forward Returns
Track forward return profiles across multiple bar horizons following triggered events.

```python
import numpy as np
import polars as pl
from ssbt.outcomes.base import BaseOutcome, check_outcome_table

class MaxDrawdownOutcome(BaseOutcome):
    """Compute maximum path drawdown within N bars following an event."""
    name = "max_drawdown"

    def compute_outcomes(self, df: pl.DataFrame, events: pl.DataFrame, params: dict) -> pl.DataFrame:
        horizons = params.get("horizons", [5, 10, 20])
        closes = df["close"].to_numpy()
        timestamps = df["timestamp"].to_numpy()
        ts_to_idx = {ts: idx for idx, ts in enumerate(timestamps)}

        rows = []
        for row in events.iter_rows(named=True):
            eid = row["event_id"]
            ts = row["timestamp"]
            if ts not in ts_to_idx:
                continue
            idx = ts_to_idx[ts]

            for h in horizons:
                if idx + h < len(closes):
                    window = closes[idx:idx + h + 1]
                    peak = np.maximum.accumulate(window)
                    dd = (window - peak) / peak
                    max_dd = float(np.min(dd))
                    rows.append({"event_id": eid, "outcome_name": self.name, "horizon": h, "value": max_dd, "diagnostics": {}})

        outcomes = pl.DataFrame(rows) if rows else pl.DataFrame(schema={"event_id": pl.Int64, "outcome_name": pl.Utf8, "horizon": pl.Int64, "value": pl.Float64, "diagnostics": pl.Object})
        check_outcome_table(outcomes)
        return outcomes
```

---

### Example 1.4: Bootstrap Statistical Confidence Intervals & Diagnostics
Evaluate statistical significance of return distributions using 2,000 bootstrap iterations.

```python
import polars as pl
from ssbt.experiments.stats import compute_confidence_stats, event_count_diagnostics
from ssbt.experiments.specs import ExperimentSpec

# Sample outcomes dataframe
outcomes = pl.DataFrame({
    "event_id": [1, 2, 3, 4, 5, 6, 7, 8],
    "horizon": [5, 5, 5, 5, 10, 10, 10, 10],
    "value": [0.02, 0.015, -0.005, 0.03, 0.04, -0.01, 0.025, 0.035]
})

spec = ExperimentSpec.from_dict({
    "version": 1,
    "experiment": {"name": "stats_test", "type": "event_study"},
    "dataset": {"source": "dummy.parquet", "symbol": "SYNTH"},
    "events": [{"name": "volume_spike"}],
    "outcomes": [{"name": "forward_return"}],
    "analysis": {"confidence": {"method": "bootstrap", "iterations": 2000, "ci": 0.95}}
})

ci_stats = compute_confidence_stats(outcomes, spec)
print("Overall Mean Estimate:", ci_stats["overall"]["mean"]["estimate"])
print("95% CI Bounds:", ci_stats["overall"]["mean"]["ci_lower"], "to", ci_stats["overall"]["mean"]["ci_upper"])
```

---

### Example 1.5: Programmatic Experiment Runner
Execute full experiment pipelines inside custom Python scripts or Jupyter Notebooks.

```python
from ssbt.experiments.runner import run_experiment

result = run_experiment("experiments/volume_spike_study.yaml")

print("Events Detected:", result["events"].height)
print("Outcomes Generated:", result["outcomes"].height)
print("Artifacts Written To:", result["output_dir"])
print("Hit Rate (5-bar):", result["statistics"]["by_horizon"]["5"]["hit_rate"])
```

---

## 2. For Systematic Traders

### Example 2.1: Single-Symbol Strategy with Complex Order Types (Trailing Stop, OCO)
Build a strategy with entry triggers and automatic trailing stop/take-profit exit protection.

```python
import numpy as np
import polars as pl
from ssbt.core.engine import Engine
from ssbt.data.feed import InMemoryFeed
from ssbt.strategy.base import BaseStrategy
from ssbt.core.events import OrderType, Side

class TrailingStopStrategy(BaseStrategy):
    def __init__(self, entry_bar=10):
        super().__init__()
        self.entry_bar = entry_bar
        self.bar_count = 0

    def on_bar(self, bar):
        self.bar_count += 1
        if self.bar_count == self.entry_bar and self.position_qty == 0:
            # Enter Long Market Order
            self.submit_order(
                symbol=bar.symbol,
                side=Side.BUY,
                type=OrderType.MARKET,
                qty=10.0
            )
            # Attach Trailing Stop (Trail by $2.00)
            self.submit_order(
                symbol=bar.symbol,
                side=Side.SELL,
                type=OrderType.TRAILING_STOP,
                qty=10.0,
                trail_offset=2.0
            )

# Create synthetic feed
df = pl.DataFrame({
    "timestamp": np.arange(100, dtype=np.int64) * 60_000_000_000,
    "symbol": ["BTCUSD"] * 100,
    "open": np.linspace(100, 150, 100),
    "high": np.linspace(101, 151, 100),
    "low": np.linspace(99, 149, 100),
    "close": np.linspace(100, 150, 100),
    "volume": [500.0] * 100,
})

engine = Engine(InMemoryFeed(df, symbol="BTCUSD"), TrailingStopStrategy())
res = engine.run()
print("Fills Recorded:", len(res.fills))
print("Final Equity:", res.final_equity)
```

---

### Example 2.2: TimeInForce Execution (IOC, FOK, GTD, DAY)
Enforce institutional order execution controls.

```python
from ssbt.core.events import Order, Side, OrderType, TimeInForce

# Immediate-Or-Cancel (IOC) Limit Order
ioc_order = Order(
    id=101,
    symbol="AAPL",
    side=Side.BUY,
    type=OrderType.LIMIT,
    qty=500.0,
    price=150.0,
    tif=TimeInForce.IOC
)

# Good-Till-Date (GTD) Order expiring at epoch nanosecond timestamp
gtd_order = Order(
    id=102,
    symbol="AAPL",
    side=Side.SELL,
    type=OrderType.LIMIT,
    qty=200.0,
    price=155.0,
    tif=TimeInForce.GTD,
    expire_at=1750000000000000000
)
```

---

### Example 2.3: Multi-Symbol Portfolio Backtesting with Custom Capital Allocation
Run portfolio strategies allocating capital dynamically across multiple tickers.

```python
import polars as pl
from ssbt.core.multi_engine import MultiSymbolEngine
from ssbt.strategy.base import BaseStrategy
from ssbt.core.events import Side, OrderType

class EqualWeightStrategy(BaseStrategy):
    def on_bar(self, bar):
        if self.position_qty == 0:
            self.submit_order(bar.symbol, Side.BUY, OrderType.MARKET, qty=10.0)

# Multi-symbol data dictionary
data_map = {
    "AAPL": pl.DataFrame({"timestamp": [1000, 2000], "symbol": ["AAPL"]*2, "open": [150.0, 152.0], "high": [153.0, 154.0], "low": [149.0, 151.0], "close": [152.0, 153.0], "volume": [1e4, 1e4]}),
    "MSFT": pl.DataFrame({"timestamp": [1000, 2000], "symbol": ["MSFT"]*2, "open": [300.0, 302.0], "high": [305.0, 306.0], "low": [299.0, 301.0], "close": [302.0, 304.0], "volume": [1e4, 1e4]}),
}

# Custom equal-weight capital allocation function
def custom_allocation(symbols, total_cash):
    alloc = total_cash / len(symbols)
    return {s: alloc for s in symbols}

engine = MultiSymbolEngine(
    data_map=data_map,
    strategy_cls=EqualWeightStrategy,
    initial_cash=200_000.0,
    allocation_fn=custom_allocation
)

results = engine.run()
print("Total Portfolio Return:", results["total_return"])
print("Per-Symbol Results:", list(results["symbol_results"].keys()))
```

---

### Example 2.4: Vectorised High-Speed Sweep Mode
Execute fast matrix parameter sweeps (3.5M+ bars/sec).

```python
from ssbt.core.vectorised import VectorisedEngine

# Run fast vectorised SMA crossover sweep across thousands of parameters
prices = np.random.randn(100_000).cumsum() + 100.0
fast_windows = [5, 10, 15, 20]
slow_windows = [30, 40, 50, 60]

results = VectorisedEngine.run_sma_sweep(prices, fast_windows, slow_windows)
print("Sweep Combinations Tested:", len(results))
```

---

## 3. For Quant Developers & Risk Managers

### Example 3.1: BacktestAdapter for Unified Metric Extraction
Convert raw backtest results directly into structured Polars DataFrames and standardized analytics.

```python
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.data.feed import ParquetFeed
from ssbt.tests.conftest import _SmaCrossStrategy

feed = ParquetFeed("ssbt/tests/data/synthetic_ohlcv.parquet", symbol="SYNTH")
strategy = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)

adapter = BacktestAdapter(initial_cash=100_000.0)
output = adapter.run_backtest(feed, strategy)

print("--- Standard Metrics ---")
print("Sharpe Ratio:  ", output["metrics"]["sharpe"])
print("Sortino Ratio: ", output["metrics"]["sortino"])
print("Max Drawdown:  ", output["metrics"]["max_drawdown"])
print("Win Rate:      ", output["metrics"]["win_rate"])
print("Profit Factor: ", output["metrics"]["profit_factor"])

print("\n--- Structured Trades DataFrame ---")
print(output["trades"].select(["symbol", "entry_time", "exit_time", "entry_price", "exit_price", "pnl", "pnl_pct"]))
```

---

### Example 3.2: Automated Chart Generation & Artifact Packaging
Export standardized PNG visualizations alongside CSV, JSON, and Parquet data artifacts.

```python
from pathlib import Path
import polars as pl
from ssbt.experiments.charts import generate_all_charts
from ssbt.experiments.specs import ExperimentSpec

outcomes = pl.DataFrame({
    "event_id": [1, 2, 3, 4],
    "horizon": [1, 1, 5, 5],
    "value": [0.01, -0.02, 0.05, -0.01]
})
events = pl.DataFrame({
    "event_id": [1, 2, 3, 4],
    "timestamp": [1000, 2000, 3000, 4000]
})
stats = {"by_horizon": {"1": {"mean": -0.005}, "5": {"mean": 0.02}}}

spec = ExperimentSpec.from_dict({
    "version": 1,
    "experiment": {"name": "chart_demo", "type": "event_study"},
    "dataset": {"source": "data.parquet", "symbol": "SYNTH"},
    "events": [{"name": "volume_spike"}],
    "outcomes": [{"name": "forward_return"}],
    "reporting": {"output_dir": "artifacts", "charts": ["distribution", "grouped_bar", "event_timeline"]}
})

chart_paths = generate_all_charts(events, outcomes, stats, spec, Path("artifacts"))
print("Generated Charts:", chart_paths)
```

---

### Example 3.3: Manifest Verification & SHA-256 Checksum Audit
Audit experiment outputs to guarantee strict reproducibility and integrity.

```python
import json
import hashlib
from pathlib import Path

manifest_path = Path("artifacts/manifest.json")
if manifest_path.exists():
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    print("Experiment:", manifest["experiment_name"])
    print("Generated At:", manifest["generated_at"])
    print("\n--- Artifact Checksums ---")
    for item in manifest["artifacts"]:
        file_path = Path("artifacts") / item["name"]
        if file_path.exists():
            computed_sha = hashlib.sha256(file_path.read_bytes()).hexdigest()
            status = "VALID" if computed_sha == item["checksum"] else "CORRUPTED"
            print(f"[{status}] {item['name']:<20} Size: {item['size']:<8} SHA: {computed_sha[:12]}...")
```
