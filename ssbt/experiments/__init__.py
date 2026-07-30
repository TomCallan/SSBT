"""Exploration engine — event/outcome plugin registry, stats, and charts.

No DSL, no file-based configuration. All experiment logic is written in Python.
"""

from ssbt.experiments.registry import Registry, RegistryError
from ssbt.experiments.stats import (
    bootstrap_ci,
    compute_confidence_stats,
    event_count_diagnostics,
    check_leakage,
)
from ssbt.experiments.charts import (
    generate_all_charts,
    generate_distribution_chart,
    generate_grouped_bar_chart,
    generate_event_timeline_chart,
    generate_matrix_heatmap_chart,
    generate_multi_equity_curve_chart,
)
from ssbt.experiments.reproducibility import capture_environment_snapshot

__all__ = [
    "Registry",
    "RegistryError",
    "bootstrap_ci",
    "compute_confidence_stats",
    "event_count_diagnostics",
    "check_leakage",
    "generate_all_charts",
    "generate_distribution_chart",
    "generate_grouped_bar_chart",
    "generate_event_timeline_chart",
    "generate_matrix_heatmap_chart",
    "generate_multi_equity_curve_chart",
    "capture_environment_snapshot",
]
