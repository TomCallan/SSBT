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

## Milestones

## M0 — Baseline Preservation
**Goal:** protect current SSBT functionality.

**Scope:**
- baseline tests
- fixture datasets
- execution flow docs

**Achievement criteria:**
- all existing backtest tests green
- no CLI behavior regressions

---

## M1 — Spec Foundation
**Goal:** introduce typed experiment specs.

**Scope:**
- YAML loader
- schema validation
- defaults resolution

**Achievement criteria:**
- valid configs parse deterministically
- invalid configs return actionable errors

---

## M2 — Plugin Contracts
**Goal:** unify event/outcome extensibility.

**Scope:**
- event/outcome base interfaces
- registry and dispatch

**Achievement criteria:**
- add a new event in one module without runner edits
- add a new outcome in one module without runner edits

---

## M3 — Vertical Slice (First Real Study)
**Goal:** ship volume spike vs forward return study.

**Scope:**
- `volume_spike` event
- `forward_return` outcome
- summary table + JSON

**Achievement criteria:**
- single command run produces deterministic artifacts
- grouped stats available by configured dimensions

---

## M4 — Statistical Confidence
**Goal:** improve interpretability and trust.

**Scope:**
- bootstrap confidence intervals
- event count diagnostics

**Achievement criteria:**
- CI reported for key metrics
- warning flags for low sample sizes

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
