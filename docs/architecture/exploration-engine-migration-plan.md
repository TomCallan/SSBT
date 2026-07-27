# Migration Plan: Backtester-First to Exploration-First

## Objective
Transition safely without breaking current SSBT backtesting workflows.

---

## Stage 1: Parallel Foundations
- Add new exploration modules under `ssbt/experiments`, `ssbt/events`, `ssbt/outcomes`.
- Do not modify core backtest execution paths yet.

Exit criteria:
- architecture modules exist and pass isolated tests.

---

## Stage 2: Shared Data/Feature Extraction
- Extract common data loading and feature logic from backtest code into shared modules.
- Backtest and exploration paths consume shared functions.

Exit criteria:
- backtest output parity maintained on regression fixtures.

---

## Stage 3: First Exploration Workflow
- Ship `volume_spike` + `forward_return` with CLI command.
- Generate artifact bundle.

Exit criteria:
- reproducible study run from YAML config.

---

## Stage 4: Backtest Adapter
- Wrap backtest execution in `experiment_type: backtest` adapter.
- Normalize outputs into unified reporting schema.

Exit criteria:
- both modes run under common orchestration layer.

---

## Stage 5: Deprecation and Cleanup
- Mark legacy-only pathways for deprecation only after stable adapter period.
- Keep compatibility shims for at least one release cycle.

Exit criteria:
- reduced duplication and documented migration notes.

---

## Risk Controls During Migration

1. Feature parity test pack
2. Output diff tooling for baseline vs migrated paths
3. Feature flags to toggle legacy/new paths
4. Progressive rollout by capability (not big-bang)
