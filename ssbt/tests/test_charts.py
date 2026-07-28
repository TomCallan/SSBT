"""Tests for chart generation and manifest integration."""

import json
from pathlib import Path
import pytest
import polars as pl
from ssbt.experiments.charts import (
    generate_distribution_chart,
    generate_grouped_bar_chart,
    generate_event_timeline_chart,
    generate_all_charts,
)
from ssbt.experiments.runner import run_experiment


def test_chart_generation(tmp_path):
    # Dummy data
    outcomes = pl.DataFrame({
        "event_id": [1, 2, 3, 4],
        "horizon": [1, 1, 5, 5],
        "value": [0.01, -0.02, 0.05, -0.01],
    })
    events = pl.DataFrame({
        "event_id": [1, 2, 3, 4],
        "timestamp": [1000, 2000, 3000, 4000],
    })
    stats = {
        "by_horizon": {
            "1": {"mean": -0.005, "median": -0.005},
            "5": {"mean": 0.02, "median": 0.02},
        }
    }

    dist_file = generate_distribution_chart(outcomes, stats, tmp_path)
    assert (tmp_path / dist_file).exists()

    bar_file = generate_grouped_bar_chart(outcomes, stats, tmp_path)
    assert (tmp_path / bar_file).exists()

    timeline_file = generate_event_timeline_chart(events, outcomes, stats, tmp_path)
    assert (tmp_path / timeline_file).exists()


def test_runner_chart_and_manifest_checksums(tmp_path):
    config_path = Path("ssbt/experiments/examples/volume_spike.yaml")
    if not config_path.exists():
        pytest.skip("volume_spike.yaml not found")

    result = run_experiment(config_path, output_dir=tmp_path)
    out_dir = result["output_dir"]
    manifest_path = out_dir / "manifest.json"

    assert manifest_path.exists()
    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    artifacts = manifest.get("artifacts", [])
    artifact_names = [a["name"] for a in artifacts]

    # Verify chart artifacts recorded in manifest with non-empty checksum and positive size
    for chart_name in ["distribution.png", "grouped_bar.png", "event_timeline.png"]:
        assert chart_name in artifact_names
        item = next(a for a in artifacts if a["name"] == chart_name)
        assert len(item["checksum"]) == 64  # sha256 hex string
        assert item["size"] > 0
