# SSBT Sub-Project 2: Job Lifecycle, Streaming & Agent Diagnostics — Design Spec

## Executive Summary
This design specification defines the architecture for **Sub-Project 2: Job Lifecycle, Streaming & Agent Diagnostics** (`ssbt.service.jobs` and `ssbt.service.diagnostics`). It extends SSBT's core service layer with async background job management, real-time event streaming queues, heartbeat timeouts, automated AI failure explanation, and standard LLM tool calling specifications.

---

## 1. Subsystems & Component Architecture

```
[ Client / AI Agent ]
         |
         +---> [ JobManager ] ---> start_job(request) / cancel_job(job_id)
         |          |
         |          +---> Background Task Loop (Engine + StreamPublisher)
         |                  |
         |                  +---> Event Queue (PROGRESS, FILL, COMPLETED, FAILED)
         |
         +---> [ Event Subscription ] ---> subscribe_job_stream(job_id)
         |
         +---> [ Agent Diagnostics ] ---> explain_failure(error)
         |
         +---> [ Tool Spec Generator ] ---> get_agent_tool_spec("openai"|"anthropic")
```

### Module Structure
- `ssbt/service/jobs.py`: `JobManager`, `JobInfo`, `JobStatus`, background task execution, streaming queues.
- `ssbt/service/diagnostics.py`: `explain_failure()` remediation mapping and `get_agent_tool_spec()`.
- `ssbt/service/observability.py`: Structured JSON logger, trace IDs, and stage timing metrics.

---

## 2. Detailed Component Specs

### 2.1 Job Lifecycle & Streaming (`ssbt/service/jobs.py`)
- `JobStatus`: Enum (`PENDING`, `RUNNING`, `CANCELLED`, `COMPLETED`, `FAILED`).
- `JobInfo`: Dataclass holding `job_id`, `status`, `progress_pct`, `created_at`, `updated_at`, `request`, `response`, `error`.
- `JobManager`:
  - `start_job(request: BacktestRequest) -> str`: Spawns async background task, assigns unique `job_id`.
  - `get_job_status(job_id: str) -> JobInfo`: Queries current job metadata and progress.
  - `cancel_job(job_id: str) -> bool`: Signals background task cancellation.
  - `subscribe_job_stream(job_id: str) -> AsyncGenerator[dict, None]`: Yields stream events in real time.
- **Heartbeat & Timeout**: Background task monitor automatically aborts jobs that exceed `request.limits.timeout_seconds` with `E_RESOURCE_LIMIT`.

### 2.2 Agent Diagnostics & LLM Tool Specifications (`ssbt/service/diagnostics.py`)
- `explain_failure(target: ErrorSpec | BacktestResponse | ServiceError | Exception) -> dict[str, Any]`:
  Maps machine error codes (`E_DATA_SCHEMA`, `E_LOOKAHEAD`, `E_STRATEGY_INIT`, `E_RESOURCE_LIMIT`, `E_RUN_NOT_FOUND`) to structured remediation steps:
  - `code`: Machine error code.
  - `summary`: Short human-readable summary.
  - `root_cause`: Specific cause derived from error details.
  - `suggested_action`: Actionable fix steps for humans or AI agents.
  - `code_fix_snippet`: Optional Python / YAML snippet showing correct usage.
- `get_agent_tool_spec(provider: str = "openai") -> list[dict[str, Any]]`:
  Generates tool definitions for `run_backtest`, `explain_failure`, `rerun`, and `compare` in OpenAI function calling or Anthropic tool format.

### 2.3 Observability & Structured Logging (`ssbt/service/observability.py`)
- `TraceLogger`: JSON-formatted logger tagging log records with `trace_id`, `run_id`, `job_id`, and `stage`.
- Stage Timing Breakdown attached to `BacktestResponse.audit`:
  `{"data_prep_ms": 12.4, "engine_run_ms": 84.1, "metrics_ms": 3.2, "total_ms": 99.7}`.

---

## 3. Verification & Testing Plan

1. **Job Lifecycle Tests (`ssbt/tests/test_service_jobs.py`)**:
   - `test_start_and_get_job_status()`: Verifies `start_job`, progress updates, and completion.
   - `test_cancel_job()`: Verifies background task cancellation.
   - `test_job_timeout()`: Asserts automatic job termination when timeout is exceeded.
   - `test_subscribe_job_stream()`: Verifies real-time event streaming from background jobs.
2. **Diagnostics & Tool Spec Tests (`ssbt/tests/test_service_diagnostics.py`)**:
   - `test_explain_failure_mapping()`: Verifies remediation guidance for all error codes.
   - `test_get_agent_tool_spec()`: Asserts valid OpenAI & Anthropic tool schema generation.
3. **Full Regression Test**:
   - Run complete pytest suite to ensure zero regressions across existing engine features.
