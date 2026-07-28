# How to Trust Results in SSBT: A Quant Due-Diligence Guide

This guide details the step-by-step procedure for verifying backtest outputs, audit trails, and statistical validity in SSBT.

---

## 1. Step 1: Run the Institutional Verification Suite

Execute the institutional due-diligence research script:

```bash
uv run python examples/institutional_due_diligence_suite.py
```

Verify that the terminal output displays `[PASS] AUDIT PASSED` and emits `simulation_assumptions_report.json`.

---

## 2. Step 2: Validate Deterministic Reproducibility

To verify that historical results are 100% reproducible and tamper-proof, execute the `rerun` utility against any artifact directory:

```bash
uv run python -m ssbt.cli.rerun artifacts/inst_run_20260728_211537
```

Confirm that the environment snapshot (Git commit SHA, branch, seed, Python platform) matches and that integrity checksums are validated.

---

## 3. Step 3: Inspect the Simulation Assumptions Report

Open `artifacts/<run_id>/simulation_assumptions_report.json` to verify that:
- Intrabar price path simulation was active (`Realistic Open -> High/Low -> Close`).
- Transaction cost parameters (slippage, commission, impact gamma) were applied.
- Point-In-Time timestamp integrity checks passed with `lookahead_leakage_detected: false`.

---

## 4. Step 4: Run the Automated Unit & Property Test Suite

Verify all accounting invariants and performance benchmarks:

```bash
uv run python -m pytest ssbt/tests/ -v
```

All 145+ unit tests must pass cleanly.
