# Audit & Reproducibility API Reference (`ssbt.analytics`)

---
summary: API reference for AuditLogger, environment snapshot capture, and point-in-time state checksum verification.
keywords: reference, audit, AuditLogger, environment snapshot, reproducibility, sha256
domain: api-reference
difficulty: intermediate
primary_apis: ssbt.analytics.AuditLogger, ssbt.capture_environment_snapshot
related_pages: /docs/index.md, /docs/reference/index.md, /docs/use-cases/deterministic-rerun-and-audit.md
---

## `ssbt.analytics.AuditLogger`

Point-in-time causality recorder emitting SHA-256 state signatures and audit trails.

```python
class AuditLogger:
    def __init__(self, enabled: bool = True)
```

### Methods
- `log_bar(bar: Bar, state_digest: str)`
- `export_artifacts(output_dir: str) -> str`

---

## `ssbt.capture_environment_snapshot`

Captures Python, Polars, Numba, OS, and CPU microarchitecture specifications.

```python
def capture_environment_snapshot() -> Dict[str, Any]
```
