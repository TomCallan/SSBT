from __future__ import annotations

import json
import logging
import time
from typing import Any


class TraceLogger:
    """Structured JSON logger with trace, run, and job context binding."""

    def __init__(
        self,
        trace_id: str | None = None,
        run_id: str | None = None,
        job_id: str | None = None,
        logger_name: str = "ssbt.service",
    ) -> None:
        self.trace_id = trace_id
        self.run_id = run_id
        self.job_id = job_id
        self.logger = logging.getLogger(logger_name)

    def log(self, level: str, event: str, **kwargs: Any) -> dict[str, Any]:
        """Log a structured JSON event tagged with trace/run/job context."""
        payload: dict[str, Any] = {"event": event}
        if self.trace_id is not None:
            payload["trace_id"] = self.trace_id
        if self.run_id is not None:
            payload["run_id"] = self.run_id
        if self.job_id is not None:
            payload["job_id"] = self.job_id
        payload.update(kwargs)

        json_msg = json.dumps(payload, default=str)
        lvl_upper = level.upper()

        if lvl_upper == "DEBUG":
            self.logger.debug(json_msg)
        elif lvl_upper in ("WARNING", "WARN"):
            self.logger.warning(json_msg)
        elif lvl_upper == "ERROR":
            self.logger.error(json_msg)
        elif lvl_upper == "CRITICAL":
            self.logger.critical(json_msg)
        else:
            self.logger.info(json_msg)

        return payload


class StageTimer:
    """Context manager for measuring stage execution durations in milliseconds."""

    def __init__(self) -> None:
        self.start_time: float | None = None
        self.end_time: float | None = None

    def __enter__(self) -> StageTimer:
        self.start_time = time.perf_counter()
        self.end_time = None
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.end_time = time.perf_counter()

    def elapsed_ms(self) -> float:
        """Return elapsed time in milliseconds."""
        if self.start_time is None:
            return 0.0
        end = self.end_time if self.end_time is not None else time.perf_counter()
        return round((end - self.start_time) * 1000.0, 3)
