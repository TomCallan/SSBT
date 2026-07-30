from __future__ import annotations

import json
import logging
import time
from typing import Any

from ssbt.quick import generate_synthetic_bars
from ssbt.service import (
    BacktestRequest,
    DataSpec,
    StageTimer,
    TraceLogger,
    run_backtest,
)


def test_stage_timer_context_manager():
    """Verify StageTimer context manager measures elapsed duration in milliseconds."""
    with StageTimer() as timer:
        time.sleep(0.01)

    elapsed = timer.elapsed_ms()
    assert isinstance(elapsed, float)
    assert elapsed >= 5.0  # Should be ~10ms


def test_trace_logger_json_formatting(caplog: Any):
    """Verify TraceLogger produces valid structured JSON log records with bound metadata."""
    caplog.set_level(logging.INFO)

    logger = TraceLogger(
        trace_id="tr-100",
        run_id="run-200",
        job_id="job-300",
        logger_name="ssbt.test_obs",
    )

    logger.log("info", "test_stage_event", bar_count=500, mode="backtest")

    assert len(caplog.records) >= 1
    record = caplog.records[-1]
    parsed = json.loads(record.message)

    assert parsed["event"] == "test_stage_event"
    assert parsed["trace_id"] == "tr-100"
    assert parsed["run_id"] == "run-200"
    assert parsed["job_id"] == "job-300"
    assert parsed["bar_count"] == 500
    assert parsed["mode"] == "backtest"


def test_trace_logger_optional_ids():
    """Verify TraceLogger handles missing trace/run/job IDs gracefully."""
    logger = TraceLogger()
    payload = logger.log("warning", "minimal_event", foo="bar")

    assert payload["event"] == "minimal_event"
    assert payload["foo"] == "bar"
    assert "trace_id" not in payload
    assert "run_id" not in payload
    assert "job_id" not in payload


def test_stage_timing_metrics_in_backtest_response():
    """Verify timing_ms breakdown is included in BacktestResponse.audit on successful backtests."""
    bars_df = generate_synthetic_bars(n_bars=30, seed=42)
    req = BacktestRequest(data=DataSpec(symbol="BTC", dataframe=bars_df))

    response = run_backtest(req)

    assert response.status == "success"
    assert "timing_ms" in response.audit

    timing = response.audit["timing_ms"]
    assert "data_prep_ms" in timing
    assert "strategy_init_ms" in timing
    assert "engine_run_ms" in timing
    assert "metrics_ms" in timing
    assert "total_ms" in timing

    for k in ("data_prep_ms", "strategy_init_ms", "engine_run_ms", "metrics_ms", "total_ms"):
        assert isinstance(timing[k], float)
        assert timing[k] >= 0.0
