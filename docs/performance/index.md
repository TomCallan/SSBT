# Performance Benchmarks & Hot-Path Tuning

---
summary: Performance benchmarks, hardware disclosure format, throughput baselines, and Numba/Polars hot-path tuning playbook.
keywords: performance, benchmarks, throughput, numba, polars, zero allocation, hot path
domain: performance-engineering
difficulty: advanced
primary_apis: ssbt.Engine, ssbt.VectorisedBacktester
related_pages: /docs/index.md, /docs/architecture/index.md
---

## Throughput Baselines

- **Single-Symbol Bar Iteration**: >1,200,000 bars/sec (x86_64, 8-core CPU)
- **Multi-Symbol Orderbook Matching**: >450,000 bars/sec
- **IPC Telemetry Stream**: >250,000 events/sec

## Hot-Path Tuning Playbook

1. **Use Pre-Allocated Arrays**: Avoid allocating list/dict objects inside `on_bar()`.
2. **Polars Lazy Evaluation**: Load parquet feeds lazily via `pl.scan_parquet()`.
3. **Numba JIT Compilation**: Core indicator loops are JIT compiled on first call.

## Hardware Disclosure Format

```json
{
  "cpu": "13th Gen Intel(R) Core(TM) i9-13900K",
  "ram_gb": 64,
  "os": "Windows 11",
  "python_version": "3.10.11",
  "polars_version": "0.20.31",
  "numba_version": "0.66.0"
}
```
