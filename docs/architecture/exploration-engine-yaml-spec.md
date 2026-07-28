# SSBT Exploration Engine — Comprehensive YAML Specification Guide

This guide provides an exhaustive reference for the **SSBT YAML Experiment Specification Format (Version 1)**. It defines every configuration parameter, validation rule, default value, and explicitly outlines **what can and cannot be built using YAML configurations alone**.

---

## Table of Contents
1. [Full Annotated Schema Reference](#1-full-annotated-schema-reference)
2. [Field-by-Field Breakdown & Validation Rules](#2-field-by-field-breakdown--validation-rules)
3. [What You CAN Build With Pure YAML Specs](#3-what-you-can-build-with-pure-yaml-specs)
4. [What You CANNOT Build With Pure YAML Specs (and How to Build It in Python)](#4-what-you-cannot-build-with-pure-yaml-specs)
5. [Complete Copy-Pasteable YAML Examples](#5-complete-copy-pasteable-yaml-examples)

---

## 1. Full Annotated Schema Reference

```yaml
version: 1 # Required: Schema specification version (Must be 1)

experiment:
  name: "volume_spike_hypothesis" # Required: Unique name of the experiment run
  type: event_study # Required: Experiment type ("event_study" or "strategy_study")
  description: "Evaluate forward returns following high-volume breakouts" # Optional

dataset:
  source: "data/synthetic_ohlcv.parquet" # Required: Path to Parquet dataset file
  symbol: "SYNTH" # Required: Symbol ticker or list of symbols
  timeframe: "1d" # Optional: Bar aggregation timeframe ("1d", "1h", "5m")
  start: "2020-01-01" # Optional: Start date filter (YYYY-MM-DD)
  end: "2033-12-31" # Optional: End date filter (YYYY-MM-DD)
  timezone: "UTC" # Optional: Timezone for timestamp parsing (Default: "UTC")
  adjustments: # Optional: Corporate action adjustment flags
    split_adjusted: true
    dividend_adjusted: true

features: [] # Optional: List of feature calculation transformers

events: # Required: List of event detection triggers (at least 1 required)
  - name: "volume_spike" # Required: Must match a registered BaseEvent plugin name
    params: # Optional: Plugin-specific keyword parameters
      window: 20
      multiplier: 2.5
      min_volume: 0
    cooldown_bars: 0 # Optional: Minimum bars to wait after trigger before new event (Default: 0)
    min_separation_bars: 1 # Optional: Enforce minimum separation between events (Default: 1)

outcomes: # Required: List of outcome metric calculators (at least 1 required)
  - name: "forward_return" # Required: Must match a registered BaseOutcome plugin name
    params:
      horizons: [1, 5, 10, 20, 50] # Forward return bar horizons

filters: # Optional: Pre-event and post-event conditional filters
  pre_event: []
  post_event: []

group_by: [] # Optional: Dimensions to group statistical aggregates by

analysis: # Optional: Statistical confidence and metric configuration
  confidence:
    method: "bootstrap" # Resampling method ("bootstrap" or "none")
    iterations: 2000 # Number of bootstrap iterations (Range: 100 to 10000)
    ci: 0.95 # Confidence interval width (Range: 0.50 to 0.99)
  statistics:
    include: ["mean", "median", "std", "hit_rate", "quantiles"]
    quantiles: [0.05, 0.25, 0.5, 0.75, 0.95]

reporting: # Optional: Output formats and visualization exports
  output_dir: "artifacts" # Directory to write generated artifacts (Default: "artifacts")
  formats: ["csv", "json", "parquet"] # Export data formats
  charts: ["distribution", "grouped_bar", "event_timeline"] # PNG charts to generate

execution: # Optional: Engine execution parameters
  seed: 42 # Random seed for deterministic bootstrap sampling (Default: 42)
  max_workers: 1 # Parallel CPU execution workers (Default: 1)
  cache_features: true # Cache feature transformers in memory (Default: true)
  fail_on_warnings: false # Fail run if validation warnings occur (Default: false)
```

---

## 2. Field-by-Field Breakdown & Validation Rules

| Section | Field | Type | Required | Default | Validation & Constraints |
|---|---|---|---|---|---|
| **Root** | `version` | Integer | **Yes** | — | Must equal `1`. |
| **experiment** | `name` | String | **Yes** | — | Non-empty identifier string. |
| | `type` | String | **Yes** | — | Must be `"event_study"` or `"strategy_study"`. |
| | `description` | String | No | `""` | Arbitrary human-readable description text. |
| **dataset** | `source` | String | **Yes** | — | Must be a valid existing path or registered feed key. |
| | `symbol` | String/List | **Yes** | — | Symbol identifier(s) present in dataset. |
| | `start` / `end` | String | No | `None` | `YYYY-MM-DD` string; `start` must be strictly `< end`. |
| **events** | `name` | String | **Yes** | — | **Must exist in the Event Registry** (`VolumeSpike`, etc.). |
| | `cooldown_bars` | Integer | No | `0` | Non-negative integer. |
| | `min_separation_bars` | Integer | No | `1` | Must be $\ge 1$. |
| **outcomes** | `name` | String | **Yes** | — | **Must exist in the Outcome Registry** (`ForwardReturn`, etc.). |
| | `params.horizons` | List[int] | No | `[1, 5, 20]` | List of positive integers representing future bar offsets. |
| **analysis** | `confidence.method` | String | No | `"none"` | Must be `"bootstrap"` or `"none"`. |
| | `confidence.iterations` | Integer | No | `2000` | Must be between `100` and `10000`. |
| | `confidence.ci` | Float | No | `0.95` | Float between `0.50` and `0.99`. |
| **reporting** | `output_dir` | String | No | `"artifacts"` | Destination directory path. |
| | `formats` | List[str] | No | `["csv", "json"]` | Allowed items: `"csv"`, `"json"`, `"parquet"`. |
| | `charts` | List[str] | No | `[]` | Allowed items: `"distribution"`, `"grouped_bar"`, `"event_timeline"`. |

---

## 3. What You CAN Build With Pure YAML Specs

Without writing a single line of Python code, you can use `ssbt-run config.yaml` to build:

1. **Multi-Horizon Hypothesis Tests**:
   Evaluate whether a technical or market signal (e.g. volume spike) leads to statistically significant price moves over 1, 5, 10, 20, or 50 future bars.
2. **Non-Parametric Statistical Confidence Audits**:
   Execute 2,000-iteration Bootstrap resampling to calculate exact 95% Confidence Intervals for expected mean return, median return, and hit rate (win percentage).
3. **Multi-Format Export Pipelines**:
   Automatically produce standardized `events.csv`, `events.parquet`, `outcomes.json`, `summary.json`, and an audited `manifest.json` with SHA-256 checksums.
4. **Automated Visualization Suites**:
   Generate publication-quality PNG charts (`distribution.png`, `grouped_bar.png`, `event_timeline.png`).

---

## 4. What You CANNOT Build With Pure YAML Specs

The YAML specification is designed for **declarative experiment configuration**. Certain dynamic logic **cannot** be defined in YAML and requires Python code:

### ❌ 1. Custom Signal Rules Not Already in the Registry
* **Why**: The YAML engine resolves event names (e.g. `name: "volume_spike"`) against Python classes registered in `Registry`.
* **Solution**: Write a Python class subclassing `BaseEvent` and register it via `Registry.register_event("my_custom_signal", MyCustomEventClass)`.

### ❌ 2. Live Bar-by-Bar Strategy Order Execution & Trailing Stop Management
* **Why**: YAML declares static event studies; it does not implement dynamic stateful order state machines (e.g. trailing stops, OCO cancellation, order modifications).
* **Solution**: Write a Python strategy class subclassing `ssbt.strategy.base.Strategy` and execute it with `Engine` or `BacktestAdapter`.

### 3. Dynamic Matrix Portfolio Capital Allocation Algorithms
* **Why**: YAML can specify multi-symbol datasets, but cannot execute dynamic linear programming or Black-Litterman matrix math for capital rebalancing.
* **Solution**: Define a custom Python allocation function `def my_allocation_fn(symbols, total_cash)` and pass it to `MultiSymbolEngine`.

### ❌ 4. External Data Downloading / API Scraping
* **Why**: SSBT decouples data ingestion from execution for performance and security.
* **Solution**: Download data in Python (e.g. via `yfinance` or CCXT), convert to a Polars DataFrame, and pass to `InMemoryFeed`.

---

## 5. Complete Copy-Pasteable YAML Examples

### Example 1: Volume Spike Hypothesis Study (`volume_spike.yaml`)
```yaml
version: 1
experiment:
  name: "volume_spike_study"
  type: event_study
  description: "Evaluate short and long term price drift following volume spikes"

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
    cooldown_bars: 0
    min_separation_bars: 1

outcomes:
  - name: "forward_return"
    params:
      horizons: [1, 5, 10, 20, 50]

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

execution:
  seed: 42
  max_workers: 1
  cache_features: true
  fail_on_warnings: false
```

### Example 2: Minimal Event Study (`minimal_study.yaml`)
```yaml
version: 1
experiment:
  name: "quick_test"
  type: event_study

dataset:
  source: "data/synthetic_ohlcv.parquet"
  symbol: "SYNTH"

events:
  - name: "volume_spike"

outcomes:
  - name: "forward_return"
```

### How to Run Any YAML Spec
```bash
ssbt-run volume_spike.yaml
```
