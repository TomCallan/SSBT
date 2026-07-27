# Exploration Engine Roadmap: Goals, Milestones, Achievements

## Vision
Build a generic research platform for market hypothesis testing where backtesting is a specialized capability.

---

## Strategic Goals

1. **Hypothesis velocity**: move from idea to test quickly.
2. **Result reliability**: reduce false conclusions via sound stats and bias controls.
3. **Reusability**: reuse data/features across event studies and backtests.
4. **Operational clarity**: standard artifacts and reproducible experiment runs.

---

## Progress Summary

```
M0 ████████████████ 100%  Baseline Preservation
M1 ████████████████ 100%  Spec Foundation
M2 ████████████████ 100%  Plugin Contracts
M3 ████████████████ 100%  Vertical Slice
M4 ████████████████ 100%  Statistical Confidence
M5 ░░░░░░░░░░░░░░░░   0%  Reporting Suite
M6 ░░░░░░░░░░░░░░░░   0%  Backtesting Integration
M7 ░░░░░░░░░░░░░░░░   0%  Hardening & Scale
```

---

---

## Milestones

## ~~M0 — Baseline Preservation~~ ✅
**Goal:** protect current SSBT functionality.

**Delivered:**
- baseline tests in `tests/test_backtest_regression.py`
- fixture datasets in `tests/fixtures/generate_fixtures.py`
- execution flow docs in `docs/current-backtest-flow.md`

**Achievement criteria:**
- [x] all existing backtest tests green
- [x] no CLI behavior regressions

---

## ~~M1 — Spec Foundation~~ ✅
**Goal:** introduce typed experiment specs.

**Delivered:**
- YAML loader with `pyyaml`
- schema validation via `pydantic`
- defaults resolution
- `experiments/spec.py` with `ExperimentSpec`, `ExperimentConfig`, `SpecLoader`

**Achievement criteria:**
- [x] valid configs parse deterministically
- [x] invalid configs return actionable errors

---

## ~~M2 — Plugin Contracts~~ ✅
**Goal:** unify event/outcome extensibility.

**Delivered:**
- `events/base.py` — `BaseEvent` ABC, `EventTableRow`, `REQUIRED_EVENT_COLUMNS`
- `outcomes/base.py` — `BaseOutcome` ABC, `OutcomeRow`, `REQUIRED_OUTCOME_COLUMNS`
- `experiments/registry.py` — `Registry` class, `RegistryError`
- 54 tests across `test_events_base.py`, `test_outcomes_base.py`, `test_registry.py`

**Achievement criteria:**
- [x] add a new event in one module without runner edits
- [x] add a new outcome in one module without runner edits

---

## ~~M3 — Vertical Slice (First Real Study)~~ ✅
**Goal:** ship volume spike vs forward return study.

**Delivered:**
- `events/volume_spike.py` — `VolumeSpike` event plugin with rolling average detection
- `outcomes/forward_return.py` — `ForwardReturn` outcome plugin with multi-horizon computation
- `experiments/runner.py` — full experiment runner: load config → resolve plugins → run events → run outcomes → compute stats → write artifacts
- CLI entry point: `ssbt run <config.yaml>` (via `ssbt.cli:main` and `ssbt-run` console script)
- Example config: `experiments/examples/volume_spike.yaml`
- Artifacts produced: events/outcomes CSVs, JSON, Parquet; `summary.json` with overall/by-horizon/by-outcome stats; `manifest.json`

**Achievement criteria:**
- [x] single command run produces deterministic artifacts
- [x] grouped stats available by configured dimensions

---

## ~~M4 — Statistical Confidence~~ ✅
**Goal:** improve interpretability and trust.

**Delivered:**
- `experiments/stats.py` — bootstrap confidence intervals (`bootstrap_ci`, `compute_confidence_stats`)
- Event count diagnostics (`event_count_diagnostics`) with horizon/outcome counts and warnings
- Anti-lookahead / data leakage checks (`check_leakage`) validating timestamps, future data access, horizon limits
- Integrated into runner: `run_experiment()` automatically computes CI, diagnostics, and leakage when configured
- Example config uses `analysis.confidence.method: bootstrap` with 2000 iterations, 95% CI

**Achievement criteria:**
- [x] CI reported for key metrics (mean, median, std, hit_rate)
- [x] warning flags for low sample sizes (event counts, outcome per horizon)
- [x] leakage checks pass (timestamps in data, no future access, horizon limits)

---

## M5 — Reporting Suite
**Goal:** standardized, shareable outputs.

**Scope:**
- CSV/JSON/Parquet artifacts
- chart generation
- manifest and checksums

**Achievement criteria:**
- complete artifact package per run
- report readability for non-authors

---

## M6 — Backtesting Integration
**Goal:** position backtesting as first-class specialized experiment.

**Scope:**
- connect backtest flow to shared data/feature layer
- map backtest metrics into unified report model

**Achievement criteria:**
- legacy backtest capabilities preserved
- shared infrastructure measurably reduces duplicated code

---

## M7 — Hardening & Scale
**Goal:** production-grade research workflow.

**Scope:**
- performance profiling
- large dataset handling
- expanded test matrix

**Achievement criteria:**
- stable runtime on high-volume datasets
- quality gates enforced in CI

---

## KPI Framework

Engineering KPIs:
- test pass rate
- median runtime per 1M bars
- memory peak thresholds
- defect escape rate

Research KPIs:
- time-to-first-result
- repeatability score (identical reruns)
- percent of studies with confidence reporting
- false-signal reduction proxies

Adoption KPIs:
- number of distinct experiment configs
- number of reusable event/outcome plugins
- user-reported friction (qualitative)

---

## Definition of Achievement (Branch-Level)

This branch is considered architecturally successful when:
1. Docs define clear interfaces and execution model.
2. YAML schema is sufficiently specific to implement directly.
3. Roadmap includes measurable exit criteria.
4. Migration path preserves existing SSBT behavior.
