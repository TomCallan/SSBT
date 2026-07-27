# SSBT Evolution Plan: From Backtester to Generic Exploration Engine

## Goal
Evolve SSBT from a pure strategy backtesting system into a generic, event-driven market exploration engine where backtesting is one experiment type among many.

### Example research question
> "I want to test the relationship between large volume spikes and price moves."

This plan introduces a research pipeline centered on:
1. Data loading/alignment
2. Event definitions
3. Outcome definitions
4. Experiment execution
5. Statistical analysis/reporting

---

## Guiding Principles

- **Keep backtesting intact** while extracting reusable components.
- **Separate concerns** between event detection, outcome measurement, and reporting.
- **Configuration-first experiments** so new studies require minimal code.
- **Reproducibility** via explicit experiment specs and deterministic data transforms.
- **Incremental delivery**: one fully working vertical slice first.

---

## Target Architecture

```text
ssbt/
  data/
  features/
  events/
    volume_spike.py
  outcomes/
    forward_return.py
    excursion.py
  experiments/
    specs.py
    runner.py
  analysis/
    stats.py
    bootstrap.py
  reports/
    tables.py
    charts.py
  backtest/
    # existing strategy/PnL logic retained
```

### Core abstractions

- `EventSpec` — Defines a trigger condition and optional preconditions.
- `OutcomeSpec` — Defines what to measure after each event.
- `ExperimentSpec` — Binds dataset, features, events, outcomes, filters, grouping.
- `ExperimentRunner` — Executes experiment and returns structured results.
- `Report` — Exports tables/charts/JSON for downstream analysis.

---

## Phased Implementation Plan

## Phase 0 — Baseline & Safety Rails

### Objectives
- Preserve current backtesting behavior.
- Add checks to prevent regressions while refactoring.

### Tasks
1. Create a lightweight architecture note describing current backtest flow.
2. Add/expand smoke tests around existing backtest CLI/API behavior.
3. Freeze representative fixture datasets for regression comparisons.

### Deliverables
- Baseline tests green.
- Documented “current-state” execution flow.

---

## Phase 1 — Introduce Experiment Specs (No behavior changes yet)

### Objectives
- Define neutral, generic experiment models.

### Tasks
1. Add `experiments/specs.py` with dataclasses/pydantic models:
   - `DatasetSpec`
   - `FeatureSpec`
   - `EventSpec`
   - `OutcomeSpec`
   - `FilterSpec`
   - `ExperimentSpec`
2. Add schema validation and clear error messages.
3. Add serializer support for YAML/JSON config files.

### Deliverables
- Load and validate experiment configs from disk.
- Unit tests for config validation.

---

## Phase 2 — Event & Outcome Plugin Interfaces

### Objectives
- Standardize how new event types and outcome metrics are added.

### Tasks
1. Add `events/base.py` with an event interface, e.g.:
   - `compute_events(df, event_spec) -> event_index_or_mask`
2. Add `outcomes/base.py` with outcome interface, e.g.:
   - `compute_outcomes(df, event_locs, outcome_spec) -> DataFrame`
3. Add registry pattern (name → implementation) for events/outcomes.

### Deliverables
- Plugin-like registration for event and outcome implementations.
- Tests proving registry dispatch works.

---

## Phase 3 — Vertical Slice: Volume Spike → Forward Return

### Objectives
- Ship one complete research workflow end-to-end.

### Tasks
1. Implement `events/volume_spike.py`:
   - Rule: `volume > k * rolling_mean(volume, window)`
   - Config params: `k`, `window`, optional minimum warmup.
2. Implement `outcomes/forward_return.py`:
   - Horizons: `[1, 5, 20]` bars (configurable).
   - Return calc on close-to-close (or configurable price field).
3. Implement `experiments/runner.py`:
   - Build needed features.
   - Evaluate event condition.
   - Compute outcomes at event timestamps.
   - Apply filters/groupings.
4. Add structured output object with:
   - event count
   - mean/median returns
   - hit rate
   - quantiles

### Deliverables
- Working “volume spike vs forward return” experiment.
- Reproducible result table from a config file.

---

## Phase 4 — Analysis & Statistical Confidence

### Objectives
- Improve quality of inferences from results.

### Tasks
1. Add `analysis/stats.py` for descriptive stats.
2. Add `analysis/bootstrap.py` for confidence intervals.
3. Optionally add parametric tests where assumptions are reasonable.
4. Add sample-size and event-frequency diagnostics.

### Deliverables
- Confidence intervals for key metrics.
- Clear statistical summary in output.

---

## Phase 5 — Reporting Layer

### Objectives
- Make findings easy to consume.

### Tasks
1. Add `reports/tables.py` for CSV/Markdown summary tables.
2. Add `reports/charts.py` for:
   - forward return distributions
   - outcome by group (regime/hour/session)
   - event frequency over time
3. Add JSON artifact for machine-readable downstream use.

### Deliverables
- Standard report bundle per experiment run.

---

## Phase 6 — CLI & UX

### Objectives
- Provide a clean command entry point for exploration workflows.

### Tasks
1. Add command:
   - `ssbt explore run --config path/to/experiment.yaml`
2. Add command:
   - `ssbt explore validate --config ...`
3. Add concise terminal summary plus artifact paths.

### Deliverables
- End-user exploration commands fully operational.

---

## Phase 7 — Integrate Backtesting as a Specialized Experiment

### Objectives
- Keep original purpose while making it one engine mode.

### Tasks
1. Adapt existing backtest flow to consume shared data/features layer.
2. Introduce “strategy simulation” as a specialized experiment type.
3. Maintain compatibility with existing backtest configs where feasible.

### Deliverables
- Backtesting remains supported and benefits from shared architecture.

---

## Example Experiment Config

```yaml
dataset: BTCUSDT_1m
features:
  - name: rolling_mean_volume
    field: volume
    window: 50
event:
  name: volume_spike
  params:
    k: 3.0
    volume_field: volume
    baseline_feature: rolling_mean_volume
outcomes:
  - name: forward_return
    params:
      price_field: close
      horizons: [1, 5, 20]
filters:
  - "session in ['NY', 'LN']"
  - "atr_14_pct > 0.5"
group_by: [regime, hour]
```

---

## MVP Scope Recommendation (First Milestone)

Target only these capabilities for the first merged milestone:
1. Config loading/validation.
2. `volume_spike` event.
3. `forward_return` outcome.
4. Runner producing summary table + JSON.
5. Basic CLI command (`explore run`).

This gives immediate research value with limited implementation risk.

---

## Risks & Mitigations

1. **Look-ahead bias**
   - Mitigation: strict forward-indexed outcome computation and warmup handling.

2. **Data alignment bugs**
   - Mitigation: centralize index alignment utilities + tests for NaN/warmup windows.

3. **Overfitting in exploratory loops**
   - Mitigation: report multiple-testing cautions and out-of-sample splits.

4. **Performance regressions on large datasets**
   - Mitigation: vectorized pandas/numpy paths first, profile hotspots, optional chunking.

5. **Architecture drift during transition**
   - Mitigation: phased rollouts and compatibility tests for existing backtests.

---

## Suggested Test Plan

- **Unit tests**
  - Event trigger correctness (`volume_spike` thresholds/warmup).
  - Outcome correctness (`forward_return` at each horizon).
  - Spec validation and registry resolution.

- **Integration tests**
  - Full run from YAML config to result artifacts.
  - Group-by/filters produce expected partitions.

- **Regression tests**
  - Existing backtest path outputs unchanged (within tolerance).

- **Bias checks**
  - Ensure no future data is used in event features/outcomes.

---

## Definition of Done

The “generic exploration engine” milestone is complete when:
- A user can define and run an event/outcome experiment from config.
- The engine outputs reproducible summary statistics and artifacts.
- At least one statistically annotated report is generated.
- Existing backtesting workflows continue to function.

---

## Immediate Next Actions

1. Scaffold `experiments/specs.py`, `events/base.py`, `outcomes/base.py`, `experiments/runner.py`.
2. Implement `events/volume_spike.py` and `outcomes/forward_return.py`.
3. Add `explore run` CLI command.
4. Add initial report output (CSV + JSON).
5. Add tests for the full vertical slice.
