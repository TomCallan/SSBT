"""Experiment specification and loading for the exploration engine."""

from ssbt.experiments.specs import (
    AnalysisSpec,
    DatasetSpec,
    EventSpec,
    ExecutionSpec,
    ExperimentSpec,
    FeatureSpec,
    FilterSpec,
    OutcomeSpec,
    ReportingSpec,
    ValidationError,
    ValidationResult,
)
from ssbt.experiments.loader import load_experiment, LoaderError
from ssbt.experiments.registry import Registry, RegistryError
from ssbt.experiments.runner import run_experiment, RunnerError
from ssbt.experiments.stats import (
    bootstrap_ci,
    event_count_diagnostics,
    check_leakage,
    compute_confidence_stats,
)
from ssbt.experiments.charts import (
    generate_distribution_chart,
    generate_grouped_bar_chart,
    generate_event_timeline_chart,
    generate_all_charts,
)

__all__ = [
    "AnalysisSpec",
    "DatasetSpec",
    "EventSpec",
    "ExecutionSpec",
    "ExperimentSpec",
    "FeatureSpec",
    "FilterSpec",
    "OutcomeSpec",
    "ReportingSpec",
    "ValidationError",
    "ValidationResult",
    "load_experiment",
    "LoaderError",
    "Registry",
    "RegistryError",
    "run_experiment",
    "RunnerError",
    "bootstrap_ci",
    "event_count_diagnostics",
    "check_leakage",
    "compute_confidence_stats",
    "generate_distribution_chart",
    "generate_grouped_bar_chart",
    "generate_event_timeline_chart",
    "generate_all_charts",
]
