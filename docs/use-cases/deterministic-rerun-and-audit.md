# Deterministic Rerun and Audit

---
summary: Auditing point-in-time causality and enforcing 100% bitwise rerun reproducibility across environments via SHA-256 signatures.
keywords: deterministic rerun, audit logger, causality, sha256 signature, environmental snapshot, reproducibility
domain: devops-qa
difficulty: intermediate
primary_apis: ssbt.analytics.AuditLogger, ssbt.cli.rerun, ssbt.capture_environment_snapshot
related_pages: /docs/use-cases/index.md, /docs/reference/audit_repro.md, /docs/reference/cli.md
---

## 1. Objective
Record full point-in-time state execution logs with `AuditLogger`, generate immutable SHA-256 state signatures, capture environment snapshots, and verify 100% deterministic rerun bit-for-bit fidelity via `uv run python -m ssbt.cli.rerun`.

## 2. Inputs
- Executed `Engine` run with `AuditLogger(enabled=True)`
- Output artifact directory containing `environment_snapshot.json` and `simulation_assumptions_report.json`

## 3. Minimal Code

```python
from ssbt import Engine, InMemoryFeed, AuditLogger, capture_environment_snapshot, generate_synthetic_bars, sma_cross

# 1. Run simulation with audit logging
df = generate_synthetic_bars(num_bars=1000, start_price=100.0, volatility=0.01, seed=42)
feed = InMemoryFeed({"BTC-USD": df})
audit_logger = AuditLogger(enabled=True)

engine = Engine(feed=feed, audit_logger=audit_logger)
result = engine.run(sma_cross)

# 2. Capture environment & audit artifacts
env_snapshot = capture_environment_snapshot()
artifact_dir = audit_logger.export_artifacts(output_dir="artifacts/inst_run_demo")

print(f"Artifact exported. Environment SHA-256: {env_snapshot['environment_hash']}")
```

To execute deterministic rerun verification via CLI:
```bash
uv run python -m ssbt.cli.rerun artifacts/inst_run_demo
```

## 4. Realistic Settings
- **State Integrity**: SHA-256 checksum recorded per bar tick across portfolio equity, position size, and order state.
- **Environment Freeze**: Logs Python version, Polars version, Numba flags, and CPU microarchitecture.

## 5. Expected Artifacts
```
artifacts/inst_run_demo/
├── audit_trail.jsonl
├── environment_snapshot.json
├── simulation_assumptions_report.json
└── checksum.sha256
```

## 6. Failure Modes
- **Stochastic Drift**: Relying on unseeded `random.random()` calls in custom strategy code breaks rerun determinism.
- **System Time Dependency**: Calling `datetime.now()` instead of `bar.timestamp`.

## 7. Validation Checks
```bash
# Verify CLI rerun exit code 0
uv run python -m ssbt.cli.rerun artifacts/inst_run_demo
# Output must read: "SUCCESS: Rerun matched original execution bit-for-bit."
```

## 8. Production Checklist
- [ ] Ensure all random number generators are seeded with explicit integer seeds.
- [ ] Confirm `simulation_assumptions_report.json` contains no unhandled warnings.
- [ ] Store `checksum.sha256` in institutional compliance storage.
