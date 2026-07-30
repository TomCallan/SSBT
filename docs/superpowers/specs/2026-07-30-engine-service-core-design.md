# SSBT Engine Service Core & Canonical Contract-First I/O — Design Spec

## Executive Summary
This design specification defines the architecture, canonical request/response contracts, pre-run safety rails, error taxonomy, and reproducibility primitives for SSBT's **Engine Service Core** (`ssbt.service`). It turns SSBT into a stable, single-entrypoint backend engine service suitable for programmatic integrations, microservices, desktop/web UIs, and autonomous AI coding agents.

---

## 1. System Architecture & Entrypoint

The service layer wraps SSBT's low-level `Engine`, `DataFeed`, `Strategy`, and `AuditLogger` components behind a unified entrypoint.

```
[ Client / Agent / UI ]
          |
          v
+-------------------------------------------------------+
| ssbt.service.run_backtest(BacktestRequest)             |
| ssbt.service.run_backtest_async(BacktestRequest)       |
+-------------------------------------------------------+
          |
          +---> [ 1. Pre-Run Safety Rail & Schema Validation ]
          |
          +---> [ 2. Deterministic Run ID & Audit Logger Setup ]
          |
          +---> [ 3. Feed Resolution & Strategy Instantiation ]
          |
          +---> [ 4. Core Engine Execution Loop ]
          |
          +---> [ 5. Metric Calculation & Artifact Archiving ]
          |
          v
 [ BacktestResponse (Structured, Machine-Readable JSON/Dict) ]
```

### Module Structure
- `ssbt/service/__init__.py`: Public API exports (`run_backtest`, `run_backtest_async`, `rerun`, `compare`).
- `ssbt/service/schemas.py`: Pydantic / dataclass definitions for request, response, and sub-configs.
- `ssbt/service/runner.py`: Core service orchestration engine.
- `ssbt/service/errors.py`: Machine-readable error codes (`E_DATA_SCHEMA`, `E_LOOKAHEAD`, etc.).
- `ssbt/service/rerun.py`: Deterministic rerun and comparison utilities.

---

## 2. Canonical Contracts (`ssbt/service/schemas.py`)

### 2.1 `BacktestRequest`
```python
@dataclass
class StrategySpec:
    name: str  # Class name or module path
    code: str | None = None  # Inline Python code if dynamic
    kwargs: dict[str, Any] = field(default_factory=dict)

@dataclass
class DataSpec:
    symbol: str
    dataframe: Any | None = None  # Polars/Pandas DataFrame
    parquet_path: str | None = None
    resample: str | None = None

@dataclass
class ExecutionSpec:
    initial_cash: float = 100_000.0
    impact_model: str | None = None
    borrow_cost: float = 0.0
    safe_mode: bool = True

@dataclass
class ResourceLimitSpec:
    max_bars: int = 1_000_000
    timeout_seconds: float = 60.0

@dataclass
class BacktestRequest:
    version: str = "1.0"
    run_id: str | None = None
    strategy: StrategySpec = field(default_factory=StrategySpec)
    data: DataSpec = field(default_factory=DataSpec)
    execution: ExecutionSpec = field(default_factory=ExecutionSpec)
    limits: ResourceLimitSpec = field(default_factory=ResourceLimitSpec)
```

### 2.2 `BacktestResponse`
```python
@dataclass
class ErrorSpec:
    code: str  # e.g., E_DATA_SCHEMA, E_LOOKAHEAD
    message: str
    hint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

@dataclass
class BacktestResponse:
    status: str  # "success" | "failed"
    run_id: str
    config_hash: str
    summary: dict[str, Any]  # total_return, sharpe, max_drawdown, n_trades, n_events
    equity_curve: list[list[float]]  # [[timestamp, equity], ...]
    fills: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    audit: dict[str, Any]  # causality_verified, sha256_signature
    artifacts: dict[str, str]  # output_dir, log_path, audit_path
    error: ErrorSpec | None = None

    def to_dict(self) -> dict[str, Any]: ...
    def to_json(self, indent: int = 2) -> str: ...
```

---

## 3. Pre-Run Safety Rails & Machine Error Codes

Before launching engine loops, `ssbt.service` executes static & schema validation.

### Error Taxonomy
| Code | Class | Cause & Remediation |
|---|---|---|
| `E_DATA_SCHEMA` | `DataError` | Missing required OHLCV/BidAsk columns or empty feed. Suggests column renames. |
| `E_STRATEGY_INIT` | `ExecutionError` | Syntax error or missing `on_bar` in strategy. Suggests template fix. |
| `E_RESOURCE_LIMIT` | `ExecutionError` | Exceeded max bars or execution timeout. |
| `E_LOOKAHEAD` | `AuditError` | Causality violation detected during execution or multi-timeframe join. |
| `E_RUN_NOT_FOUND` | `SSBTError` | Specified `run_id` artifact folder missing for rerun. |

---

## 4. Reproducibility & Rerun Primitives

- `ssbt.service.rerun(run_id: str) -> BacktestResponse`:
  Locates saved run folder (`artifacts/<run_id>/`), restores `environment_snapshot.json` and `simulation_assumptions_report.json`, and executes backtest with identical parameters.
- `ssbt.service.compare(run_id_a: str, run_id_b: str) -> dict`:
  Generates a delta report comparing equity curves, Sharpe ratio divergence, trade counts, and fill PnL differences.

---

## 5. Verification Plan

### Automated Tests
1. **Service API Tests (`ssbt/tests/test_service.py`)**:
   - `test_run_backtest_sync()`: Validates `run_backtest` with valid `BacktestRequest`.
   - `test_run_backtest_async()`: Validates `run_backtest_async` coroutine execution.
   - `test_pre_run_validation_errors()`: Asserts proper return of `E_DATA_SCHEMA` and `E_STRATEGY_INIT` error codes.
   - `test_rerun_and_compare()`: Verifies deterministic rerun matching and comparison delta output.
2. **Full Regression Test**:
   - Run complete 190-test pytest suite to verify zero regressions across existing engine components.
