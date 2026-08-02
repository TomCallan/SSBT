# Error Catalog & Remediation Guide

---
summary: Error catalog listing error codes, probable causes, remediation steps, and minimal reproducible diagnosis commands.
keywords: errors, error catalog, remediation, debugging, exception handling
domain: developer-experience
difficulty: beginner-to-advanced
primary_apis: ssbt.service.explain_failure
related_pages: /docs/index.md, /docs/cookbook/index.md
---

## Error Catalog

### `ERR_UNSORTED_TIMESTAMPS`
- **Probable Cause**: Bar DataFrame timestamps are not in strictly ascending order.
- **Remediation**: Sort DataFrame by timestamp: `df = df.sort("timestamp")`.
- **Diagnosis Command**: `uv run ssbt validate --data bars.parquet`

### `ERR_LOOKAHEAD_DETECTED`
- **Probable Cause**: Multi-timeframe join used forward looking join strategy.
- **Remediation**: Use `align_multi_timeframe()` which enforces backward `asof` join.

### `ERR_INSUFFICIENT_LIQUIDITY`
- **Probable Cause**: Order volume exceeds `max_participation` cap under `RealisticExecutionEngine`.
- **Remediation**: Reduce trade quantity or increase participation cap.

### `ERR_DETERMINISM_MISMATCH`
- **Probable Cause**: Rerun state signature diverged from original run snapshot.
- **Remediation**: Ensure strategy does not call non-deterministic external IO or unseeded `random` functions.
- **Diagnosis Command**: `uv run python -m ssbt.cli.rerun <artifact_dir>`
