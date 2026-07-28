"""Unit tests for AuditLogger."""

import polars as pl
import pytest
from ssbt.analytics.audit import AuditLogger


def test_audit_event_outcomes_valid():
    events = pl.DataFrame({
        "event_id": [1, 2, 3],
        "timestamp": [1000, 2000, 3000],
        "symbol": ["SYNTH", "SYNTH", "SYNTH"]
    })
    outcomes = pl.DataFrame({
        "event_id": [1, 1, 2, 3],
        "horizon": [1, 5, 1, 5],
        "value": [0.01, 0.02, -0.01, 0.03]
    })

    logger = AuditLogger(verbose=False)
    is_valid, violations = logger.verify_event_outcomes(events, outcomes)
    assert is_valid
    assert len(violations) == 0


def test_audit_event_outcomes_invalid_lookahead():
    events = pl.DataFrame({
        "event_id": [1, 2],
        "timestamp": [1000, 2000],
        "symbol": ["SYNTH", "SYNTH"]
    })
    outcomes = pl.DataFrame({
        "event_id": [1, 2],
        "horizon": [-1, 5],  # Negative horizon -> lookahead error
        "value": [0.01, 0.02]
    })

    logger = AuditLogger(verbose=False)
    is_valid, violations = logger.verify_event_outcomes(events, outcomes)
    assert not is_valid
    assert any("non-positive horizons" in v for v in violations)


def test_audit_generate_report(tmp_path):
    events = pl.DataFrame({
        "event_id": [1, 2],
        "timestamp": [1000, 2000],
        "symbol": ["SYNTH", "SYNTH"]
    })
    outcomes = pl.DataFrame({
        "event_id": [1, 2],
        "horizon": [1, 5],
        "value": [0.01, 0.02]
    })

    logger = AuditLogger(verbose=False)
    report = logger.generate_report(events=events, outcomes=outcomes, output_dir=tmp_path)

    assert report.is_valid
    assert (tmp_path / "audit_trail.json").exists()


def test_sync_latest_run_folder(tmp_path):
    from ssbt.analytics.audit import sync_latest_run_folder
    run_dir = tmp_path / "run_test_01"
    run_dir.mkdir()
    (run_dir / "sample.txt").write_text("hello world")

    latest = sync_latest_run_folder(run_dir, target_dir=tmp_path / "latest")
    assert latest.exists()
    assert (latest / "sample.txt").read_text() == "hello world"
