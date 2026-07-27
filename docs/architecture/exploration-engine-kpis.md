# Exploration Engine KPIs and Success Metrics

## 1) Product/Research KPIs

- **Hypothesis cycle time**: median time from new YAML spec to first results.
- **Experiment repeatability**: percent of reruns producing matching summary outputs under pinned data.
- **Coverage of analysis**: percent of experiments with confidence intervals enabled.
- **Insight yield proxy**: number of experiments that pass minimum evidence thresholds.

---

## 2) Engineering KPIs

- **Build health**: CI pass rate on main development branch.
- **Runtime performance**: median runtime per 1M bars by experiment type.
- **Memory efficiency**: peak memory usage at defined dataset scales.
- **Extensibility velocity**: time to add a new event or outcome plugin including tests.

---

## 3) Quality KPIs

- **Leakage incidents**: count of detected look-ahead violations.
- **Regression stability**: parity score for legacy backtest outputs.
- **Validation quality**: number of config errors caught pre-run.

---

## 4) Adoption KPIs

- Number of active experiment specs
- Number of unique plugin types used
- Frequency of grouped/conditional analyses

---

## 5) Target Bands (Initial)

- Repeatability: >= 99% deterministic match for pinned runs
- CI coverage: >= 80% of exploratory studies
- Time-to-first-result: <= 10 minutes for standard local dataset
- Backtest parity: <= agreed tolerance drift on core metrics

---

## 6) Quarterly Review Template

For each quarter, report:
1. KPI trend table
2. top regressions and root causes
3. architectural debt prioritized list
4. next-quarter improvement commitments
