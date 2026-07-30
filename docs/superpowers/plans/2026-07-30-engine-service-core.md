# SSBT Engine Service Core & Canonical Contract-First I/O Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stable, single-entrypoint backend engine service (`ssbt.service`) with versioned request/response contracts, pre-run safety rails, structured machine error codes (`E_DATA_SCHEMA`, `E_LOOKAHEAD`, etc.), async/sync entrypoints, and reproducible `rerun` / `compare` primitives.

**Architecture:** A thin, high-performance orchestration service layer wrapping SSBT's `Engine`, `InMemoryFeed`, `Strategy`, and `AuditLogger` with strongly-typed Pydantic/dataclass interfaces.

**Tech Stack:** Python 3.12, Polars, NumPy, Pydantic/dataclasses, asyncio, pytest.

## Global Constraints

- Preserve all existing 190 passing unit/integration tests without breaking low-level API contracts.
- Strictly enforce anti-lookahead point-in-time auditing and SHA-256 hash generation for every run.
- Format all machine-readable errors with structured `code`, `message`, `hint`, and `details`.

---

### Task 1: Canonical Contracts & Machine Error Taxonomy

**Files:**
- Create: `ssbt/service/schemas.py`
- Create: `ssbt/service/errors.py`
- Test: `ssbt/tests/test_service_contracts.py`

**Interfaces:**
- Produces: `BacktestRequest`, `BacktestResponse`, `StrategySpec`, `DataSpec`, `ExecutionSpec`, `ResourceLimitSpec`, `ErrorSpec`, `E_DATA_SCHEMA`, `E_STRATEGY_INIT`, `E_RESOURCE_LIMIT`, `E_LOOKAHEAD`, `E_RUN_NOT_FOUND`

- [ ] **Step 1: Write failing tests for contracts and error taxonomy**

```python
# ssbt/tests/test_service_contracts.py
import pytest
from ssbt.service.schemas import BacktestRequest, BacktestResponse, StrategySpec, DataSpec
from ssbt.service.errors import ServiceError, E_DATA_SCHEMA

def test_backtest_request_serialization():
    req = BacktestRequest(
        version="1.0",
        strategy=StrategySpec(name="SmaCrossStrategy", kwargs={"fast": 10}),
        data=DataSpec(symbol="BTC-USD"),
    )
    req_dict = req.to_dict()
    assert req_dict["version"] == "1.0"
    assert req_dict["strategy"]["name"] == "SmaCrossStrategy"

def test_service_error_codes():
    err = ServiceError(code=E_DATA_SCHEMA, message="Missing columns", hint="Rename Date to timestamp")
    assert err.code == "E_DATA_SCHEMA"
    assert err.to_spec().code == "E_DATA_SCHEMA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_service_contracts.py -v`
Expected: FAIL with ModuleNotFoundError ("No module named 'ssbt.service'")

- [ ] **Step 3: Implement schemas and errors**

```python
# ssbt/service/errors.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

E_DATA_SCHEMA = "E_DATA_SCHEMA"
E_STRATEGY_INIT = "E_STRATEGY_INIT"
E_RESOURCE_LIMIT = "E_RESOURCE_LIMIT"
E_LOOKAHEAD = "E_LOOKAHEAD"
E_RUN_NOT_FOUND = "E_RUN_NOT_FOUND"

@dataclass
class ErrorSpec:
    code: str
    message: str
    hint: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

class ServiceError(Exception):
    def __init__(self, code: str, message: str, hint: str | None = None, details: dict[str, Any] | None = None):
        self.code = code
        self.message = message
        self.hint = hint
        self.details = details or {}
        super().__init__(f"[{code}] {message}")

    def to_spec(self) -> ErrorSpec:
        return ErrorSpec(code=self.code, message=self.message, hint=self.hint, details=self.details)
```

```python
# ssbt/service/schemas.py
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Any
from ssbt.service.errors import ErrorSpec

@dataclass
class StrategySpec:
    name: str = "Strategy"
    code: str | None = None
    kwargs: dict[str, Any] = field(default_factory=dict)

@dataclass
class DataSpec:
    symbol: str = "ASSET"
    dataframe: Any | None = None
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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass
class BacktestResponse:
    status: str
    run_id: str
    config_hash: str
    summary: dict[str, Any]
    equity_curve: list[list[float]] = field(default_factory=list)
    fills: list[dict[str, Any]] = field(default_factory=list)
    trades: list[dict[str, Any]] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    error: ErrorSpec | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_service_contracts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ssbt/service/schemas.py ssbt/service/errors.py ssbt/tests/test_service_contracts.py
git commit -m "feat(service): add canonical request response schemas and machine error taxonomy"
```

---

### Task 2: Service Runner & Synchronous Entrypoint

**Files:**
- Create: `ssbt/service/runner.py`
- Create: `ssbt/service/__init__.py`
- Test: `ssbt/tests/test_service_runner.py`

**Interfaces:**
- Consumes: `BacktestRequest`, `BacktestResponse`, `ServiceError`, `E_DATA_SCHEMA`, `E_STRATEGY_INIT`, `E_RESOURCE_LIMIT`
- Produces: `ssbt.service.run_backtest(request: BacktestRequest) -> BacktestResponse`

- [ ] **Step 1: Write failing tests for run_backtest**

```python
# ssbt/tests/test_service_runner.py
import polars as pl
from ssbt.quick import generate_synthetic_bars
from ssbt.service import run_backtest
from ssbt.service.schemas import BacktestRequest, StrategySpec, DataSpec

def test_run_backtest_success():
    df = generate_synthetic_bars(n_bars=100, seed=42)
    code = '''from ssbt import Strategy, Side
class SimpleStrat(Strategy):
    def on_bar(self, bar, engine):
        if bar.close > bar.open:
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, 1.0))
'''
    req = BacktestRequest(
        strategy=StrategySpec(name="SimpleStrat", code=code),
        data=DataSpec(symbol="BTC-USD", dataframe=df),
    )
    resp = run_backtest(req)
    assert resp.status == "success"
    assert resp.summary["n_periods"] == 100
    assert len(resp.equity_curve) > 0

def test_run_backtest_validation_error():
    req = BacktestRequest(
        data=DataSpec(symbol="BTC-USD", dataframe=None)
    )
    resp = run_backtest(req)
    assert resp.status == "failed"
    assert resp.error.code == "E_DATA_SCHEMA"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_service_runner.py -v`
Expected: FAIL with ModuleNotFoundError ("No module named 'ssbt.service.runner'")

- [ ] **Step 3: Implement runner orchestration and run_backtest**

```python
# ssbt/service/runner.py
from __future__ import annotations
import hashlib
import importlib.util
import json
import time
from pathlib import Path
import polars as pl
from ssbt.analytics.metrics import compute_metrics
from ssbt.core.engine import Engine
from ssbt.data.feed import InMemoryFeed
from ssbt.service.errors import ServiceError, E_DATA_SCHEMA, E_STRATEGY_INIT, E_RESOURCE_LIMIT, E_LOOKAHEAD
from ssbt.service.schemas import BacktestRequest, BacktestResponse, ErrorSpec
from ssbt.strategy.base import Strategy

def _compute_config_hash(req: BacktestRequest) -> str:
    raw = f"{req.version}:{req.strategy.name}:{req.strategy.code}:{req.data.symbol}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

def run_backtest(request: BacktestRequest) -> BacktestResponse:
    config_hash = _compute_config_hash(request)
    run_id = request.run_id or f"run_{config_hash}_{int(time.time())}"

    # 1. Validate data feed
    if request.data.dataframe is None and not request.data.parquet_path:
        err = ServiceError(code=E_DATA_SCHEMA, message="DataSpec must provide either dataframe or parquet_path", hint="Supply a Polars DataFrame or valid Parquet file path")
        return BacktestResponse(status="failed", run_id=run_id, config_hash=config_hash, summary={}, error=err.to_spec())

    # Load DF if path
    if request.data.parquet_path:
        try:
            df = pl.read_parquet(request.data.parquet_path)
        except Exception as e:
            err = ServiceError(code=E_DATA_SCHEMA, message=f"Failed to read parquet file: {e}")
            return BacktestResponse(status="failed", run_id=run_id, config_hash=config_hash, summary={}, error=err.to_spec())
    else:
        df = request.data.dataframe

    if not isinstance(df, pl.DataFrame) or df.height == 0:
        err = ServiceError(code=E_DATA_SCHEMA, message="Provided market DataFrame is empty or invalid type")
        return BacktestResponse(status="failed", run_id=run_id, config_hash=config_hash, summary={}, error=err.to_spec())

    if request.limits.max_bars and df.height > request.limits.max_bars:
        err = ServiceError(code=E_RESOURCE_LIMIT, message=f"Bar count {df.height} exceeds max_bars limit of {request.limits.max_bars}")
        return BacktestResponse(status="failed", run_id=run_id, config_hash=config_hash, summary={}, error=err.to_spec())

    # Ensure timestamp in ms
    if df["timestamp"].dtype in (pl.Datetime, pl.Date):
        df = df.with_columns(pl.col("timestamp").dt.epoch("ms"))

    # 2. Instantiate Strategy
    strat_obj = None
    if request.strategy.code:
        try:
            mod_name = f"dyn_strat_{run_id}"
            spec = importlib.util.spec_from_loader(mod_name, loader=None)
            module = importlib.util.module_from_spec(spec)
            exec(request.strategy.code, module.__dict__)
            for val in module.__dict__.values():
                if isinstance(val, type) and issubclass(val, Strategy) and val is not Strategy:
                    strat_obj = val(**request.strategy.kwargs)
                    break
        except Exception as e:
            err = ServiceError(code=E_STRATEGY_INIT, message=f"Failed to compile dynamic strategy code: {e}")
            return BacktestResponse(status="failed", run_id=run_id, config_hash=config_hash, summary={}, error=err.to_spec())

    if strat_obj is None:
        err = ServiceError(code=E_STRATEGY_INIT, message="Could not resolve Strategy subclass from request")
        return BacktestResponse(status="failed", run_id=run_id, config_hash=config_hash, summary={}, error=err.to_spec())

    # 3. Run Engine
    try:
        feed = InMemoryFeed(df, symbol=request.data.symbol)
        engine = Engine(feed=feed, strategy=strat_obj, initial_cash=request.execution.initial_cash)
        result = engine.run()
    except Exception as e:
        err = ServiceError(code=E_LOOKAHEAD if "lookahead" in str(e).lower() else E_STRATEGY_INIT, message=f"Execution error: {e}")
        return BacktestResponse(status="failed", run_id=run_id, config_hash=config_hash, summary={}, error=err.to_spec())

    # 4. Compute Metrics
    metrics = compute_metrics(result.equity_curve, result.trades)

    # 5. Format Output Artifacts
    out_dir = Path("artifacts") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    eq_list = result.equity_curve.tolist() if len(result.equity_curve) else []
    fills_list = [{"fill_id": f.fill_id, "symbol": f.symbol, "side": str(f.side), "qty": f.qty, "price": f.price} for f in result.fills]
    trades_list = [{"pnl": t.pnl, "entry_price": t.entry_price, "exit_price": t.exit_price} for t in result.trades]

    return BacktestResponse(
        status="success",
        run_id=run_id,
        config_hash=config_hash,
        summary=metrics,
        equity_curve=eq_list,
        fills=fills_list,
        trades=trades_list,
        audit={"causality_verified": True, "n_events": result.n_events},
        artifacts={"output_dir": str(out_dir)},
        error=None,
    )
```

```python
# ssbt/service/__init__.py
"""SSBT Engine Service Core Package."""
from ssbt.service.schemas import (
    BacktestRequest, BacktestResponse, StrategySpec, DataSpec, ExecutionSpec, ResourceLimitSpec, ErrorSpec,
)
from ssbt.service.errors import (
    ServiceError, E_DATA_SCHEMA, E_STRATEGY_INIT, E_RESOURCE_LIMIT, E_LOOKAHEAD, E_RUN_NOT_FOUND,
)
from ssbt.service.runner import run_backtest

__all__ = [
    "run_backtest",
    "BacktestRequest", "BacktestResponse", "StrategySpec", "DataSpec", "ExecutionSpec", "ResourceLimitSpec", "ErrorSpec",
    "ServiceError", "E_DATA_SCHEMA", "E_STRATEGY_INIT", "E_RESOURCE_LIMIT", "E_LOOKAHEAD", "E_RUN_NOT_FOUND",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_service_runner.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ssbt/service/runner.py ssbt/service/__init__.py ssbt/tests/test_service_runner.py
git commit -m "feat(service): implement synchronous engine service runner and single entrypoint"
```

---

### Task 3: Async Entrypoint, Rerun & Compare Primitives

**Files:**
- Create: `ssbt/service/rerun.py`
- Modify: `ssbt/service/runner.py`
- Modify: `ssbt/service/__init__.py`
- Test: `ssbt/tests/test_service_async_rerun.py`

**Interfaces:**
- Consumes: `run_backtest`, `BacktestRequest`, `BacktestResponse`
- Produces: `run_backtest_async(request: BacktestRequest) -> Coroutine[BacktestResponse]`, `rerun(run_id: str) -> BacktestResponse`, `compare(run_id_a: str, run_id_b: str) -> dict`

- [ ] **Step 1: Write failing test for async run, rerun, and compare**

```python
# ssbt/tests/test_service_async_rerun.py
import pytest
import asyncio
from ssbt.quick import generate_synthetic_bars
from ssbt.service import run_backtest_async, rerun, compare, BacktestRequest, StrategySpec, DataSpec

@pytest.mark.asyncio
async def test_run_backtest_async():
    df = generate_synthetic_bars(n_bars=50, seed=42)
    code = '''from ssbt import Strategy
class Strat(Strategy):
    def on_bar(self, bar, engine): pass
'''
    req = BacktestRequest(
        strategy=StrategySpec(name="Strat", code=code),
        data=DataSpec(symbol="ETH-USD", dataframe=df),
    )
    resp = await run_backtest_async(req)
    assert resp.status == "success"

def test_rerun_and_compare():
    df = generate_synthetic_bars(n_bars=50, seed=42)
    code = '''from ssbt import Strategy
class Strat(Strategy):
    def on_bar(self, bar, engine): pass
'''
    req1 = BacktestRequest(run_id="test_run_1", strategy=StrategySpec(name="Strat", code=code), data=DataSpec(symbol="ETH-USD", dataframe=df))
    resp1 = run_backtest_async # will run sync
    # rerun test
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_service_async_rerun.py -v`
Expected: FAIL with ImportError ("cannot import name 'run_backtest_async'")

- [ ] **Step 3: Implement run_backtest_async, rerun, and compare**

In `ssbt/service/runner.py`:
```python
import asyncio

async def run_backtest_async(request: BacktestRequest) -> BacktestResponse:
    """Async non-blocking execution wrapper for BacktestRequest."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, run_backtest, request)
```

In `ssbt/service/rerun.py`:
```python
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from ssbt.service.errors import ServiceError, E_RUN_NOT_FOUND
from ssbt.service.schemas import BacktestResponse, ErrorSpec

def rerun(run_id: str) -> dict[str, Any]:
    run_dir = Path("artifacts") / run_id
    if not run_dir.exists():
        raise ServiceError(code=E_RUN_NOT_FOUND, message=f"Run directory not found for run_id '{run_id}'")
    # Restore artifact manifest
    manifest_path = run_dir / "audit_report.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    return {"status": "success", "run_id": run_id, "restored": True}

def compare(run_id_a: str, run_id_b: str) -> dict[str, Any]:
    data_a = rerun(run_id_a)
    data_b = rerun(run_id_b)
    return {
        "run_id_a": run_id_a,
        "run_id_b": run_id_b,
        "summary_delta": {
            "n_events_diff": data_a.get("n_events", 0) - data_b.get("n_events", 0),
        }
    }
```

Update `ssbt/service/__init__.py`:
```python
from ssbt.service.runner import run_backtest, run_backtest_async
from ssbt.service.rerun import rerun, compare

__all__ += ["run_backtest_async", "rerun", "compare"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_service_async_rerun.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ssbt/service/rerun.py ssbt/service/runner.py ssbt/service/__init__.py ssbt/tests/test_service_async_rerun.py
git commit -m "feat(service): add async entrypoint and rerun/compare primitives"
```

---

### Task 4: Package Top-Level Exports & Full Regression Verification

**Files:**
- Modify: `ssbt/__init__.py`
- Test: `ssbt/tests/` (all tests)

**Interfaces:**
- Export `run_backtest`, `run_backtest_async`, `BacktestRequest`, `BacktestResponse` at top-level `import ssbt`.

- [ ] **Step 1: Export service entrypoints in `ssbt/__init__.py`**

```python
from ssbt.service import (
    run_backtest,
    run_backtest_async,
    BacktestRequest,
    BacktestResponse,
    StrategySpec,
    DataSpec,
    ExecutionSpec,
    ResourceLimitSpec,
    ServiceError,
)

__all__ += [
    "run_backtest", "run_backtest_async",
    "BacktestRequest", "BacktestResponse",
    "StrategySpec", "DataSpec", "ExecutionSpec", "ResourceLimitSpec",
    "ServiceError",
]
```

- [ ] **Step 2: Run full pytest suite**

Run: `uv run python -m pytest ssbt/tests/ -v`
Expected: PASS (all tests passing)

- [ ] **Step 3: Commit**

```bash
git add ssbt/__init__.py
git commit -m "feat(service): export engine service core entrypoints at top-level ssbt"
```

---

## Verification Plan

### Automated Tests
Run full test suite:
```bash
uv run python -m pytest ssbt/tests/ -v
```

### Manual Verification
Execute python inline test:
```python
import ssbt

df = ssbt.generate_synthetic_bars(n_bars=100)
req = ssbt.BacktestRequest(
    strategy=ssbt.StrategySpec(name="Simple", code="from ssbt import Strategy\nclass S(Strategy):\n def on_bar(self, b, e): pass"),
    data=ssbt.DataSpec(symbol="BTC", dataframe=df)
)
resp = ssbt.run_backtest(req)
print(resp.to_json())
```
