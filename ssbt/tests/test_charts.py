"""Tests for chart generation (event study charts)."""

import polars as pl
from ssbt.experiments.charts import (
    generate_distribution_chart,
    generate_grouped_bar_chart,
    generate_event_timeline_chart,
    generate_all_charts,
)


def test_chart_generation(tmp_path):
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
