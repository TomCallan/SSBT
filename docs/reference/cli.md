# CLI & Deterministic Rerun API Reference (`ssbt.cli`)

---
summary: API reference for SSBT Command-Line Interface (CLI) tools and deterministic rerun verifier module.
keywords: reference, cli, rerun, ssbt run, ssbt validate, python -m ssbt.cli.rerun
domain: api-reference
difficulty: intermediate
primary_apis: ssbt.cli.rerun
related_pages: /docs/index.md, /docs/reference/index.md, /docs/use-cases/deterministic-rerun-and-audit.md
---

## Deterministic Rerun Verifier CLI

```bash
uv run python -m ssbt.cli.rerun <artifact_dir>
```

### Parameters
- `<artifact_dir>`: Path to audit artifact folder containing `audit_trail.jsonl`, `environment_snapshot.json`, and `checksum.sha256`.

### Exit Codes
- `0`: Success — Rerun matched original run bit-for-bit.
- `1`: Failure — Deterministic state mismatch or environmental hash drift detected.

---

## SSBT CLI Commands

### `ssbt run`
Runs a backtest simulation from CLI using a strategy file and parquet dataset.

```bash
uv run ssbt run --strategy strategy.py --data bars.parquet --out artifacts/cli_run
```

### `ssbt validate`
Validates schema, timestamp monotonicity, and point-in-time join integrity for a dataset.

```bash
uv run ssbt validate --data bars.parquet
```
