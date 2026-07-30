from __future__ import annotations

import asyncio
import polars as pl
import pytest

from ssbt.quick import generate_synthetic_bars
from ssbt.service import (
    E_DATA_SCHEMA,
    E_RESOURCE_LIMIT,
    E_RUN_NOT_FOUND,
    BacktestRequest,
    DataSpec,
    JobInfo,
    JobManager,
    JobStatus,
    ResourceLimitSpec,
    ServiceError,
    cancel_job,
    get_job_status,
    start_job,
    subscribe_job_stream,
)


@pytest.fixture(autouse=True)
def reset_job_manager():
    """Ensure JobManager state is cleared before and after each test."""
    JobManager.get_instance().clear()
    yield
    JobManager.get_instance().clear()


def test_start_job_and_get_job_status_success():
    async def _runner():
        df = generate_synthetic_bars(n_bars=30, seed=42)
        req = BacktestRequest(
            data=DataSpec(symbol="BTC-USD", dataframe=df),
        )

        job_id = await start_job(req)
        assert isinstance(job_id, str)
        assert len(job_id) > 0

        # Retrieve status immediately
        info = get_job_status(job_id)
        assert info.job_id == job_id
        assert info.status in (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.COMPLETED)

        # Wait for completion
        for _ in range(50):
            info = get_job_status(job_id)
            if info.status == JobStatus.COMPLETED:
                break
            await asyncio.sleep(0.05)

        assert info.status == JobStatus.COMPLETED
        assert info.progress_pct == 100.0
        assert info.response is not None
        assert info.response.status == "success"
        assert info.error is None

        # Test dictionary serialization
        d = info.to_dict()
        assert d["job_id"] == job_id
        assert d["status"] == "COMPLETED"
        assert d["progress_pct"] == 100.0

    asyncio.run(_runner())


def test_get_job_status_missing_job_id():
    with pytest.raises(ServiceError) as exc_info:
        get_job_status("nonexistent_job_999")
    assert exc_info.value.code == E_RUN_NOT_FOUND


def test_cancel_job_success():
    async def _runner():
        df = generate_synthetic_bars(n_bars=100, seed=42)
        req = BacktestRequest(
            data=DataSpec(symbol="ETH-USD", dataframe=df),
        )

        job_id = await start_job(req)
        success = cancel_job(job_id)
        assert success is True

        info = get_job_status(job_id)
        assert info.status == JobStatus.CANCELLED

        # Subsequent cancellation returns False
        second_cancel = cancel_job(job_id)
        assert second_cancel is False

    asyncio.run(_runner())


def test_cancel_job_missing_job_id():
    with pytest.raises(ServiceError) as exc_info:
        cancel_job("nonexistent_job_888")
    assert exc_info.value.code == E_RUN_NOT_FOUND


def test_subscribe_job_stream():
    async def _runner():
        df = generate_synthetic_bars(n_bars=20, seed=100)
        req = BacktestRequest(
            data=DataSpec(symbol="SOL-USD", dataframe=df),
        )

        job_id = await start_job(req)

        events = []
        async for event in subscribe_job_stream(job_id):
            events.append(event)

        assert len(events) >= 2
        assert events[0]["event"] == "snapshot"
        assert events[0]["job_id"] == job_id

        final_event = events[-1]
        assert final_event["event"] == "job_completed"
        assert final_event["status"] == "COMPLETED"
        assert final_event["progress_pct"] == 100.0

    asyncio.run(_runner())


def test_subscribe_job_stream_missing_job_id():
    async def _runner():
        with pytest.raises(ServiceError) as exc_info:
            async for _ in subscribe_job_stream("nonexistent_job_777"):
                pass
        assert exc_info.value.code == E_RUN_NOT_FOUND

    asyncio.run(_runner())


def test_job_failure_handling():
    async def _runner():
        req = BacktestRequest(
            data=DataSpec(symbol="FAIL-USD", dataframe=pl.DataFrame()),
        )

        job_id = await start_job(req)

        for _ in range(50):
            info = get_job_status(job_id)
            if info.status == JobStatus.FAILED:
                break
            await asyncio.sleep(0.05)

        info = get_job_status(job_id)
        assert info.status == JobStatus.FAILED
        assert info.error is not None
        assert info.error.code == E_DATA_SCHEMA

    asyncio.run(_runner())


def test_job_timeout_monitoring():
    async def _runner():
        df = generate_synthetic_bars(n_bars=50, seed=1)
        req = BacktestRequest(
            data=DataSpec(symbol="TIMEOUT-USD", dataframe=df),
            limits=ResourceLimitSpec(timeout_seconds=0.00001),
        )

        job_id = await start_job(req)

        for _ in range(50):
            info = get_job_status(job_id)
            if info.status == JobStatus.FAILED:
                break
            await asyncio.sleep(0.05)

        info = get_job_status(job_id)
        assert info.status == JobStatus.FAILED
        assert info.error is not None
        assert info.error.code == E_RESOURCE_LIMIT

    asyncio.run(_runner())
