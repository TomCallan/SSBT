from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, AsyncGenerator, Dict, Optional, Set
import uuid

from ssbt.service.errors import (
    E_RESOURCE_LIMIT,
    E_RUN_NOT_FOUND,
    ErrorSpec,
    ServiceError,
)
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
    progress_pct: float
    created_at: str
    updated_at: str
    request: BacktestRequest
    response: Optional[BacktestResponse] = None
    error: Optional[ErrorSpec] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value if isinstance(self.status, Enum) else str(self.status),
            "progress_pct": self.progress_pct,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "request": self.request.to_dict() if hasattr(self.request, "to_dict") else asdict(self.request),
            "response": self.response.to_dict() if self.response and hasattr(self.response, "to_dict") else (asdict(self.response) if self.response else None),
            "error": asdict(self.error) if self.error else None,
        }


class JobManager:
    """Singleton managing backtest background execution, job state tracking, timeout monitoring, and event streams."""

    _instance: Optional[JobManager] = None

    def __new__(cls) -> JobManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._jobs: Dict[str, JobInfo] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._initialized = True

    @classmethod
    def get_instance(cls) -> JobManager:
        return cls()

    def clear(self) -> None:
        """Reset all internal state (for testing)."""
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._jobs.clear()
        self._tasks.clear()
        self._subscribers.clear()

    async def start_job(self, request: BacktestRequest) -> str:
        job_id = request.run_id or f"job_{uuid.uuid4().hex[:12]}"
        request.run_id = job_id
        now = datetime.now(timezone.utc).isoformat()

        job_info = JobInfo(
            job_id=job_id,
            status=JobStatus.PENDING,
            progress_pct=0.0,
            created_at=now,
            updated_at=now,
            request=request,
        )
        self._jobs[job_id] = job_info
        self._subscribers[job_id] = set()

        task = asyncio.create_task(self._run_job(job_id, request))
        self._tasks[job_id] = task

        self._broadcast_event(job_id, {
            "event": "job_pending",
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "progress_pct": 0.0,
            "timestamp": now,
        })
        return job_id

    def get_job_status(self, job_id: str) -> JobInfo:
        if job_id not in self._jobs:
            raise ServiceError(
                code=E_RUN_NOT_FOUND,
                message=f"Job '{job_id}' not found",
                hint="Verify job_id or ensure job was started via start_job()",
            )
        return self._jobs[job_id]

    def cancel_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            raise ServiceError(
                code=E_RUN_NOT_FOUND,
                message=f"Job '{job_id}' not found",
                hint="Verify job_id before attempting cancellation",
            )
        job_info = self._jobs[job_id]
        if job_info.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return False

        now = datetime.now(timezone.utc).isoformat()
        job_info.status = JobStatus.CANCELLED
        job_info.updated_at = now

        task = self._tasks.get(job_id)
        if task and not task.done():
            task.cancel()

        self._broadcast_event(job_id, {
            "event": "job_cancelled",
            "job_id": job_id,
            "status": JobStatus.CANCELLED.value,
            "progress_pct": job_info.progress_pct,
            "timestamp": now,
        })
        return True

    async def subscribe_job_stream(self, job_id: str) -> AsyncGenerator[dict, None]:
        if job_id not in self._jobs:
            raise ServiceError(
                code=E_RUN_NOT_FOUND,
                message=f"Job '{job_id}' not found",
                hint="Ensure job was started before subscribing to event stream",
            )

        queue: asyncio.Queue = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = set()
        self._subscribers[job_id].add(queue)

        job_info = self._jobs[job_id]
        snapshot_event = {
            "event": "snapshot",
            "job_id": job_id,
            "status": job_info.status.value if isinstance(job_info.status, Enum) else str(job_info.status),
            "progress_pct": job_info.progress_pct,
            "timestamp": job_info.updated_at,
        }
        yield snapshot_event

        if job_info.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            self._subscribers[job_id].discard(queue)
            return

        try:
            while True:
                event = await queue.get()
                yield event
                event_type = event.get("event")
                status = event.get("status")
                if event_type in ("job_completed", "job_failed", "job_cancelled") or status in (
                    JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.CANCELLED.value
                ):
                    break
        finally:
            if job_id in self._subscribers:
                self._subscribers[job_id].discard(queue)

    def _broadcast_event(self, job_id: str, event: dict) -> None:
        subscribers = self._subscribers.get(job_id, set())
        for q in list(subscribers):
            q.put_nowait(event)

    async def _run_job(self, job_id: str, request: BacktestRequest) -> None:
        job_info = self._jobs[job_id]

        now = datetime.now(timezone.utc).isoformat()
        job_info.status = JobStatus.RUNNING
        job_info.progress_pct = 10.0
        job_info.updated_at = now

        self._broadcast_event(job_id, {
            "event": "job_running",
            "job_id": job_id,
            "status": JobStatus.RUNNING.value,
            "progress_pct": 10.0,
            "timestamp": now,
        })

        timeout_sec = request.limits.timeout_seconds if request.limits else 60.0

        try:
            if job_info.status == JobStatus.CANCELLED:
                return

            response = await asyncio.wait_for(run_backtest_async(request), timeout=timeout_sec)

            if job_info.status == JobStatus.CANCELLED:
                return

            now = datetime.now(timezone.utc).isoformat()
            job_info.updated_at = now
            job_info.response = response

            if response.status == "success":
                job_info.status = JobStatus.COMPLETED
                job_info.progress_pct = 100.0
                job_info.error = None

                self._broadcast_event(job_id, {
                    "event": "job_completed",
                    "job_id": job_id,
                    "status": JobStatus.COMPLETED.value,
                    "progress_pct": 100.0,
                    "summary": response.summary,
                    "timestamp": now,
                })
            else:
                job_info.status = JobStatus.FAILED
                job_info.progress_pct = 100.0
                job_info.error = response.error

                self._broadcast_event(job_id, {
                    "event": "job_failed",
                    "job_id": job_id,
                    "status": JobStatus.FAILED.value,
                    "progress_pct": 100.0,
                    "error": response.error.to_dict() if hasattr(response.error, "to_dict") else asdict(response.error) if response.error else None,
                    "timestamp": now,
                })

        except asyncio.CancelledError:
            now = datetime.now(timezone.utc).isoformat()
            job_info.status = JobStatus.CANCELLED
            job_info.updated_at = now
            self._broadcast_event(job_id, {
                "event": "job_cancelled",
                "job_id": job_id,
                "status": JobStatus.CANCELLED.value,
                "progress_pct": job_info.progress_pct,
                "timestamp": now,
            })
            raise
        except asyncio.TimeoutError:
            now = datetime.now(timezone.utc).isoformat()
            job_info.status = JobStatus.FAILED
            job_info.progress_pct = 100.0
            job_info.updated_at = now
            err_spec = ErrorSpec(
                code=E_RESOURCE_LIMIT,
                message=f"Job '{job_id}' exceeded execution timeout of {timeout_sec}s",
                hint="Increase ResourceLimitSpec.timeout_seconds or optimize strategy/dataset",
                details={"timeout_seconds": timeout_sec},
            )
            job_info.error = err_spec
            self._broadcast_event(job_id, {
                "event": "job_failed",
                "job_id": job_id,
                "status": JobStatus.FAILED.value,
                "progress_pct": 100.0,
                "error": asdict(err_spec),
                "timestamp": now,
            })
        except Exception as e:
            now = datetime.now(timezone.utc).isoformat()
            job_info.status = JobStatus.FAILED
            job_info.progress_pct = 100.0
            job_info.updated_at = now
            err_spec = ErrorSpec(
                code="E_INTERNAL_ERROR",
                message=f"Unhandled internal error during job execution: {e}",
                hint="Check system logs and exception trace",
                details={"error": str(e)},
            )
            job_info.error = err_spec
            self._broadcast_event(job_id, {
                "event": "job_failed",
                "job_id": job_id,
                "status": JobStatus.FAILED.value,
                "progress_pct": 100.0,
                "error": asdict(err_spec),
                "timestamp": now,
            })


async def start_job(request: BacktestRequest) -> str:
    return await JobManager.get_instance().start_job(request)


def get_job_status(job_id: str) -> JobInfo:
    return JobManager.get_instance().get_job_status(job_id)


def cancel_job(job_id: str) -> bool:
    return JobManager.get_instance().cancel_job(job_id)


def subscribe_job_stream(job_id: str) -> AsyncGenerator[dict, None]:
    return JobManager.get_instance().subscribe_job_stream(job_id)
