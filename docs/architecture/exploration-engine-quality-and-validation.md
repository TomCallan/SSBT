# Quality, Validation, and Scientific Guardrails

## 1) Testing Strategy

## Unit Tests
- Event correctness under edge thresholds/warmup
- Outcome correctness by horizon and field
- Spec parser and defaults
- Registry lookup and plugin conflicts

## Integration Tests
- End-to-end run from YAML to artifacts
- Multi-group aggregation correctness
- Filter semantics (`pre_event`, `post_event`)

## Regression Tests
- Existing backtest output consistency
- Deterministic artifact equivalence under fixed seed/data

## Performance Tests
- Benchmark event scanning on 1M+ bars
- Memory profile for multi-horizon outcomes

---

## 2) Bias and Leakage Controls

1. **Temporal discipline**
   - Features available at `t` must not include future data.
2. **Outcome isolation**
   - Outcomes start strictly after event timestamp.
3. **Warmup enforcement**
   - Exclude periods lacking full feature windows.
4. **Data snooping warnings**
   - Flag high parameter sweep volumes without holdout.
5. **Optional holdout support**
   - Train/explore window vs validation window split.

---

## 3) Statistical Validation

Minimum required outputs:
- `n_events`
- mean, median, std
- hit rate
- configured quantiles
- confidence intervals (if enabled)

Recommended warnings:
- low event count threshold breach
- confidence interval too wide
- highly skewed distribution caution

---

## 4) Reproducibility Rules

Each run must record:
- resolved config
- dataset fingerprint
- code version (git SHA)
- execution seed
- environment metadata (python version, library versions)

---

## 5) CI Quality Gates (Suggested)

1. Lint/type checks pass
2. Unit + integration tests pass
3. Determinism test passes for fixed fixture
4. Performance benchmark under ceiling (configurable)

---

## 6) Acceptance Checklist per New Plugin

For each new event/outcome plugin:
- docs added
- schema example added
- unit tests added
- at least one integration scenario added
- no look-ahead proof in tests
