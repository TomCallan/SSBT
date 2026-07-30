# Exploration Engine Architecture (SSBT)

## 1) Purpose
Define a durable architecture that evolves SSBT from a backtesting-first system into a generic **market exploration engine** where strategy backtests are one experiment modality.

---

## 2) Architectural Goals

1. **Generality**: Any hypothesis should be representable as Event → Outcome(s).
2. **Reproducibility**: Same config + same data version yields same outputs.
3. **Extensibility**: New events/outcomes/reporters added without core rewrites.
4. **Performance**: Handle large OHLCV datasets with vectorized paths.
5. **Integrity**: Enforce no look-ahead leakage by construction.
6. **Backward compatibility**: Preserve current backtesting workflows.

---

## 3) Layered System Design

```text
┌────────────────────────────────────────────────────────────────────┐
│ Interface Layer                                                    │
│ - CLI (`ssbt explore ...`)                                         │
│ - Python API                                                       │
└────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Orchestration Layer                                                │
│ - ExperimentSpec loader/validator                                  │
│ - ExperimentRunner                                                 │
│ - Artifact manager                                                 │
└────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Domain Layer                                                       │
│ - Event plugins                                                    │
│ - Outcome plugins                                                  │
│ - Filter/grouping engine                                           │
│ - Regime/tag calculators                                           │
└────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Data & Feature Layer                                               │
│ - Dataset adapters (csv/parquet/exchange exports)                 │
│ - Time alignment/index integrity                                   │
│ - Feature graph/cache                                               │
└────────────────────────────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────────────┐
│ Analysis & Reporting Layer                                         │
│ - Descriptive stats                                                │
│ - Confidence estimation (bootstrap)                                │
│ - Tables/charts/JSON manifests                                     │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4) Core Contracts

## 4.1 Event Contract
Input: canonical DataFrame + event params + optional features
Output: boolean mask or indexed event table with metadata

Required fields in event table:
- `event_id`
- `timestamp`
- `symbol` (if multi-asset)
- `event_name`
- `event_meta` (JSON-like dict)

## 4.2 Outcome Contract
Input: canonical DataFrame + event table + outcome params
Output: one row per event per outcome horizon/metric

Required fields:
- `event_id`
- `outcome_name`
- `horizon`
- `value`
- optional diagnostics (`insufficient_future_bars`, etc.)

## 4.3 Runner Contract
Input: validated `ExperimentSpec`
Output: `ExperimentResult` object + artifact bundle

`ExperimentResult` minimum:
- run metadata (run_id, git_sha if available, timestamps)
- event summary
- outcome summary
- grouped summary tables
- artifact paths

---

## 5) Canonical Data Model

Single-asset minimum columns:
- `timestamp` (tz-aware UTC)
- `open`, `high`, `low`, `close`, `volume`

Optional:
- `symbol`
- `vwap`, `trade_count`, `bid_ask_spread`

Rules:
- Monotonic increasing index
- No duplicate timestamps per symbol
- Explicit handling policy for gaps/missing bars

---

## 6) Dependency Rules

1. `events/` and `outcomes/` must not depend on `reports/`.
2. `analysis/` consumes runner outputs; does not mutate raw events.
3. `backtest/` may depend on shared `data/`, `features/`, and `experiments/specs`.
4. CLI is thin: parse args, call orchestrator, render summary.

---

## 7) Execution Pipeline (Runtime)

1. Parse JSON config.
2. Validate schema and defaults.
3. Resolve dataset and feature dependencies.
4. Materialize features.
5. Detect events.
6. Compute outcomes.
7. Apply filters/grouping.
8. Compute stats + CIs.
9. Write artifacts + manifest.
10. Print deterministic run summary.

---

## 8) Artifact Model

Per run directory:

```text
artifacts/<run_id>/
  manifest.json
  config.resolved.json
  events.parquet
  outcomes.parquet
  summary_overall.csv
  summary_grouped.csv
  stats.json
  charts/
```

`manifest.json` includes:
- spec hash
- dataset fingerprint/version
- code version (commit SHA)
- artifact checksums

---

## 9) Extension Mechanisms

- Plugin registry for events and outcomes by unique name.
- Optional entrypoint-based plugin loading (future).
- Versioned plugin interface (`api_version`) for compatibility.

---

## 10) Backtesting as a Specialized Experiment

Define `experiment_type: backtest` with dedicated outcome families:
- trade-level metrics
- equity curve metrics
- drawdown metrics

This keeps existing SSBT strengths while sharing core data/feature infrastructure.

---

## 11) Non-Functional Targets

- 1M bars single-symbol event scan within practical local runtime.
- Zero silent leakage: all future-looking ops must be explicit and audited.
- Re-run determinism under pinned data + params.

---

## 12) ADR Recommendations

Create ADRs for:
1. Canonical data schema
2. Event/outcome plugin interface
3. Artifact format + manifest
4. Backtest-as-experiment decision
