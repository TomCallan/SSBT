# SSBT Sub-Project 2: Job Lifecycle, Streaming & Agent Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build background job lifecycle management (`ssbt.service.jobs`), real-time streaming queues, heartbeat/timeout orchestration, automated AI error remediation (`explain_failure`), LLM tool calling specifications (`get_agent_tool_spec`), and stage timing observability.

**Architecture:** Async background job registry managing event stream queues, wrapped with structured diagnostics and JSON observability extensions.

**Tech Stack:** Python 3.12, asyncio, dataclasses, pytest, pytest-asyncio.

## Global Constraints

- Preserve all existing 208 passing unit/integration tests without breaking low-level API contracts.
- Job management must be thread-safe and non-blocking for background job monitoring.
- Diagnostics must cover all error codes (`E_DATA_SCHEMA`, `E_STRATEGY_INIT`, `E_RESOURCE_LIMIT`, `E_LOOKAHEAD`, `E_RUN_NOT_FOUND`).

---

### Task 1: Job Lifecycle Manager & Async Streaming

**Files:**
- Create: `ssbt/service/jobs.py`
- Test: `ssbt/tests/test_service_jobs.py`

**Interfaces:**
- Produces: `JobStatus`, `JobInfo`, `JobManager`, `start_job`, `get_job_status`, `cancel_job`, `subscribe_job_stream`

- [ ] **Step 1: Write failing tests for JobManager**

```python
# ssbt/tests/test_service_jobs.py
import pytest
import asyncio
from ssbt.quick import generate_synthetic_bars
from ssbt.service import BacktestRequest, DataSpec
from ssbt.service.jobs import (
    JobManager, JobStatus, start_job, get_job_status, cancel_job, subscribe_job_stream,
)

@pytest.mark.asyncio
async def test_job_lifecycle_flow():
    bars_df = generate_synthetic_bars(n_bars=50, seed=42)
    req = BacktestRequest(data=DataSpec(symbol="BTC", dataframe=bars_df))
    job_id = await start_job(req)
    assert job_id is not None
    info = get_job_status(job_id)
    assert info.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_service_jobs.py -v`
Expected: FAIL with ModuleNotFoundError ("No module named 'ssbt.service.jobs'")

- [ ] **Step 3: Implement JobManager and streaming functions**

```python
# ssbt/service/jobs.py
from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator
import uuid

from ssbt.service.errors import ServiceError, E_RUN_NOT_FOUND
from ssbt.service.runner import run_backtest_async
from ssbt.service.schemas import BacktestRequest, BacktestResponse

class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class JobInfo:
    job_id: str
    status: JobStatus
    progress_pct: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    request: BacktestRequest | None = None
    response: BacktestResponse | None = None
    error: str | None = None

class JobManager:
    _instance: JobManager | None = None

    def __init__(self):
        self._jobs: dict[str, JobInfo] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._streams: dict[str, list[asyncio.Queue]] = {}

    @classmethod
    def get_instance(cls) -> JobManager:
        if cls._instance is None:
            cls._instance = JobManager()
        return cls._instance

    async def start_job(self, request: BacktestRequest) -> str:
        job_id = request.run_id or f"job_{uuid.uuid4().hex[:12]}"
        info = JobInfo(job_id=job_id, status=JobStatus.PENDING, request=request)
        self._jobs[job_id] = info
        self._streams[job_id] = []

        task = asyncio.create_task(self._run_job_task(job_id, request))
        self._tasks[job_id] = task
        return job_id

    async def _run_job_task(self, job_id: str, request: BacktestRequest) -> None:
        info = self._jobs[job_id]
        info.status = JobStatus.RUNNING
        info.updated_at = datetime.now(timezone.utc).isoformat()
        self._emit_event(job_id, {"event": "STATUS_CHANGED", "status": JobStatus.RUNNING})

        try:
            timeout = request.limits.timeout_seconds if request.limits else 60.0
            resp = await asyncio.wait_for(run_backtest_async(request), timeout=timeout)
            info.response = resp
            if resp.status == "success":
                info.status = JobStatus.COMPLETED
                info.progress_pct = 100.0
                self._emit_event(job_id, {"event": "COMPLETED", "response": resp.to_dict()})
            else:
                info.status = JobStatus.FAILED
                info.error = resp.error.message if resp.error else "Execution failed"
                self._emit_event(job_id, {"event": "FAILED", "error": info.error})
        except asyncio.CancelledError:
            info.status = JobStatus.CANCELLED
            self._emit_event(job_id, {"event": "CANCELLED"})
        except asyncio.TimeoutError:
            info.status = JobStatus.FAILED
            info.error = f"Job timed out after {request.limits.timeout_seconds}s"
            self._emit_event(job_id, {"event": "FAILED", "error": info.error})
        except Exception as e:
            info.status = JobStatus.FAILED
            info.error = str(e)
            self._emit_event(job_id, {"event": "FAILED", "error": str(e)})

    def get_job_status(self, job_id: str) -> JobInfo:
        if job_id not in self._jobs:
            raise ServiceError(code=E_RUN_NOT_FOUND, message=f"Job ID '{job_id}' not found")
        return self._jobs[job_id]

    def cancel_job(self, job_id: str) -> bool:
        if job_id in self._tasks:
            self._tasks[job_id].cancel()
            return True
        return False

    def _emit_event(self, job_id: str, event_payload: dict) -> None:
        if job_id in self._streams:
            for q in self._streams[job_id]:
                q.put_nowait(event_payload)

    async def subscribe_job_stream(self, job_id: str) -> AsyncGenerator[dict, None]:
        if job_id not in self._jobs:
            raise ServiceError(code=E_RUN_NOT_FOUND, message=f"Job ID '{job_id}' not found")
        q: asyncio.Queue = asyncio.Queue()
        self._streams[job_id].append(q)
        try:
            while True:
                evt = await q.get()
                yield evt
                if evt.get("event") in ("COMPLETED", "FAILED", "CANCELLED"):
                    break
        finally:
            if job_id in self._streams and q in self._streams[job_id]:
                self._streams[job_id].remove(q)

async def start_job(request: BacktestRequest) -> str:
    return await JobManager.get_instance().start_job(request)

def get_job_status(job_id: str) -> JobInfo:
    return JobManager.get_instance().get_job_status(job_id)

def cancel_job(job_id: str) -> bool:
    return JobManager.get_instance().cancel_job(job_id)

async def subscribe_job_stream(job_id: str) -> AsyncGenerator[dict, None]:
    async for evt in JobManager.get_instance().subscribe_job_stream(job_id):
        yield evt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_service_jobs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ssbt/service/jobs.py ssbt/tests/test_service_jobs.py
git commit -m "feat(service): implement JobManager, async job lifecycle, and real-time streaming"
```

---

### Task 2: AI Agent Failure Diagnostics & LLM Tool Specifications

**Files:**
- Create: `ssbt/service/diagnostics.py`
- Test: `ssbt/tests/test_service_diagnostics.py`

**Interfaces:**
- Produces: `explain_failure(target)` and `get_agent_tool_spec(provider)`

- [ ] **Step 1: Write failing tests for diagnostics and tool specs**

```python
# ssbt/tests/test_service_diagnostics.py
from ssbt.service.diagnostics import explain_failure, get_agent_tool_spec
from ssbt.service.errors import ErrorSpec, E_DATA_SCHEMA, E_LOOKAHEAD

def test_explain_failure_data_schema():
    err = ErrorSpec(code=E_DATA_SCHEMA, message="Missing columns", hint="Rename Close to close")
    diag = explain_failure(err)
    assert diag["code"] == "E_DATA_SCHEMA"
    assert "suggested_action" in diag
    assert "code_fix_snippet" in diag

def test_get_agent_tool_spec():
    spec_openai = get_agent_tool_spec("openai")
    assert isinstance(spec_openai, list)
    assert any(t["function"]["name"] == "run_backtest" for t in spec_openai)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_service_diagnostics.py -v`
Expected: FAIL with ModuleNotFoundError ("No module named 'ssbt.service.diagnostics'")

- [ ] **Step 3: Implement explain_failure and get_agent_tool_spec**

```python
# ssbt/service/diagnostics.py
from __future__ import annotations
from typing import Any
from ssbt.service.errors import (
    ErrorSpec, ServiceError, E_DATA_SCHEMA, E_STRATEGY_INIT, E_RESOURCE_LIMIT, E_LOOKAHEAD, E_RUN_NOT_FOUND,
)
from ssbt.service.schemas import BacktestResponse

def explain_failure(target: ErrorSpec | BacktestResponse | ServiceError | Exception) -> dict[str, Any]:
    """Provide automated diagnostic explanations and code fix hints for AI agents."""
    err_spec: ErrorSpec | None = None
    if isinstance(target, ErrorSpec):
        err_spec = target
    elif isinstance(target, BacktestResponse) and target.error:
        err_spec = target.error
    elif isinstance(target, ServiceError):
        err_spec = target.to_spec()
    elif isinstance(target, Exception):
        err_spec = ErrorSpec(code="E_UNKNOWN", message=str(target))

    if not err_spec:
        return {"status": "no_error", "message": "Backtest completed without errors"}

    code = err_spec.code
    msg = err_spec.message
    hint = err_spec.hint or ""

    remediations = {
        E_DATA_SCHEMA: {
            "summary": "Market data feed schema validation failure",
            "root_cause": f"The provided DataFrame or file does not match required OHLCV/BidAsk schema. Details: {msg}",
            "suggested_action": "Ensure DataFrame contains columns: ['timestamp', 'open', 'high', 'low', 'close', 'volume']. Rename any capitalized column names.",
            "code_fix_snippet": "df = df.rename({'Date': 'timestamp', 'Close': 'close'})",
        },
        E_STRATEGY_INIT: {
            "summary": "Strategy compilation or initialization error",
            "root_cause": f"The strategy code failed to compile or instantiate. Details: {msg}",
            "suggested_action": "Check strategy syntax and ensure a subclass inheriting from `ssbt.Strategy` and implementing `on_bar(self, bar, engine)` is defined.",
            "code_fix_snippet": "from ssbt import Strategy\nclass MyStrat(Strategy):\n    def on_bar(self, bar, engine):\n        pass",
        },
        E_RESOURCE_LIMIT: {
            "summary": "Resource ceiling or timeout limit exceeded",
            "root_cause": f"Execution exceeded bar count or timeout threshold. Details: {msg}",
            "suggested_action": "Increase ResourceLimitSpec.max_bars or timeout_seconds, or slice the input dataset.",
            "code_fix_snippet": "req.limits.max_bars = 5_000_000",
        },
        E_LOOKAHEAD: {
            "summary": "Anti-lookahead causality audit violation",
            "root_cause": f"Causality error detected in data timestamps or strategy logic. Details: {msg}",
            "suggested_action": "Verify point-in-time joins and avoid negative `.shift()` operations in signal calculations.",
            "code_fix_snippet": "use ssbt.align_multi_timeframe(lower_df, higher_df)",
        },
        E_RUN_NOT_FOUND: {
            "summary": "Run ID or artifact directory missing",
            "root_cause": f"Requested run_id does not exist in artifacts directory. Details: {msg}",
            "suggested_action": "Check run_id identifier or verify artifact folder exists under 'artifacts/<run_id>'.",
            "code_fix_snippet": "payload = ssbt.rerun('run_valid_id')",
        },
    }

    info = remediations.get(code, {
        "summary": "General execution error",
        "root_cause": msg,
        "suggested_action": hint or "Inspect trace logs and request payload parameters.",
        "code_fix_snippet": "",
    })

    return {
        "code": code,
        "message": msg,
        "hint": hint,
        "summary": info["summary"],
        "root_cause": info["root_cause"],
        "suggested_action": info["suggested_action"],
        "code_fix_snippet": info["code_fix_snippet"],
    }

def get_agent_tool_spec(provider: str = "openai") -> list[dict[str, Any]]:
    """Return JSON Schema tool definitions for LLM function calling."""
    tools = [
        {
            "type": "function",
            "function": {
                "name": "run_backtest",
                "description": "Execute single-pass quantitative strategy backtest using SSBT engine.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "run_id": {"type": "string", "description": "Optional unique run identifier."},
                        "symbol": {"type": "string", "description": "Ticker symbol identifier."},
                        "strategy_code": {"type": "string", "description": "Python source code implementing ssbt.Strategy."},
                        "initial_cash": {"type": "number", "description": "Starting portfolio cash."},
                    },
                    "required": ["symbol", "strategy_code"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "explain_failure",
                "description": "Analyze an SSBT engine error code and return remediation instructions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "error_code": {"type": "string", "description": "Machine error code (e.g. E_DATA_SCHEMA, E_LOOKAHEAD)."},
                    },
                    "required": ["error_code"],
                },
            },
        },
    ]
    return tools
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_service_diagnostics.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ssbt/service/diagnostics.py ssbt/tests/test_service_diagnostics.py
git commit -m "feat(service): add automated AI agent diagnostics and LLM tool calling specifications"
```

---

### Task 3: Observability & Stage Timing Metrics

**Files:**
- Create: `ssbt/service/observability.py`
- Modify: `ssbt/service/runner.py`
- Test: `ssbt/tests/test_service_observability.py`

**Interfaces:**
- Produces: `TraceLogger`, stage timing tracking attached to `BacktestResponse.audit["timing_ms"]`

- [ ] **Step 1: Write failing test for stage timing observability**

```python
# ssbt/tests/test_service_observability.py
from ssbt.quick import generate_synthetic_bars
from ssbt.service import run_backtest, BacktestRequest, DataSpec

def test_stage_timing_metrics():
    bars_df = generate_synthetic_bars(n_bars=30, seed=42)
    req = BacktestRequest(data=DataSpec(symbol="BTC", dataframe=bars_df))
    resp = run_backtest(req)
    assert resp.status == "success"
    assert "timing_ms" in resp.audit
    assert "total_ms" in resp.audit["timing_ms"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_service_observability.py -v`
Expected: FAIL with KeyError ("timing_ms")

- [ ] **Step 3: Implement observability module and integrate with runner**

```python
# ssbt/service/observability.py
from __future__ import annotations
import json
import logging
import time
from typing import Any

class TraceLogger:
    def __init__(self, trace_id: str):
        self.trace_id = trace_id
        self.logger = logging.getLogger("ssbt.service")

    def log(self, level: str, event: str, **kwargs: Any) -> None:
        payload = {"trace_id": self.trace_id, "event": event, **kwargs}
        if level.lower() == "error":
            self.logger.error(json.dumps(payload, default=str))
        else:
            self.logger.info(json.dumps(payload, default=str))
```

In `ssbt/service/runner.py`:
Track timestamps around data prep, strategy compilation, engine execution, and metrics calculation, storing `timing_ms` dictionary in `BacktestResponse.audit["timing_ms"]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_service_observability.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ssbt/service/observability.py ssbt/service/runner.py ssbt/tests/test_service_observability.py
git commit -m "feat(service): add structured JSON observability logging and stage timing metrics"
```

---

### Task 4: Package Top-Level Exports & Full Regression Verification

**Files:**
- Modify: `ssbt/service/__init__.py`
- Modify: `ssbt/__init__.py`
- Test: `ssbt/tests/` (all tests)

- [ ] **Step 1: Export sub-project 2 entrypoints in `ssbt/service/__init__.py` and `ssbt/__init__.py`**

Export: `JobManager`, `JobStatus`, `JobInfo`, `start_job`, `get_job_status`, `cancel_job`, `subscribe_job_stream`, `explain_failure`, `get_agent_tool_spec`, `TraceLogger`.

- [ ] **Step 2: Run full pytest suite**

Run: `uv run python -m pytest ssbt/tests/ -v`
Expected: PASS (all tests passing)

- [ ] **Step 3: Commit**

```bash
git add ssbt/service/__init__.py ssbt/__init__.py
git commit -m "feat(service): export job lifecycle streaming diagnostics and tool specs at top-level ssbt"
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
import asyncio
import ssbt

async def main():
    df = ssbt.generate_synthetic_bars(n_bars=100)
    req = ssbt.BacktestRequest(data=ssbt.DataSpec(symbol="BTC", dataframe=df))
    job_id = await ssbt.start_job(req)
    info = ssbt.get_job_status(job_id)
    print("Job status:", info.status)
    diag = ssbt.explain_failure(ssbt.ErrorSpec(code=ssbt.E_DATA_SCHEMA, message="test"))
    print("Diagnosis:", diag)

asyncio.run(main())
```
