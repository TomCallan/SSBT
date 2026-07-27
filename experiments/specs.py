"""Experiment config dataclass models with validation.

Mirrors the YAML spec in docs/architecture/exploration-engine-yaml-spec.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@dataclass
class ValidationError:
    """Single validation issue."""

    path: str
    message: str
    suggestion: str | None = None


ValidationResult = list[ValidationError]


# ---------------------------------------------------------------------------
# Config sections
# ---------------------------------------------------------------------------
@dataclass
class DatasetSpec:
    """Dataset definition."""

    source: str
    symbol: str | list[str]
    timeframe: str
    start: str | None = None
    end: str | None = None
    timezone: str = "UTC"
    adjustments: dict[str, bool] | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> DatasetSpec:
        return DatasetSpec(
            source=data["source"],
            symbol=data.get("symbol", ""),
            timeframe=data.get("timeframe", ""),
            start=data.get("start"),
            end=data.get("end"),
            timezone=data.get("timezone", "UTC"),
            adjustments=data.get("adjustments"),
        )

    def validate(self) -> ValidationResult:
        errors: ValidationResult = []
        if not self.source:
            errors.append(ValidationError(
                path="dataset.source",
                message="dataset.source is required",
                suggestion="Set a parquet path or data source name.",
            ))
        if self.start and self.end and self.start >= self.end:
            errors.append(ValidationError(
                path="dataset.start",
                message=f"dataset.start ({self.start}) must be before dataset.end ({self.end})",
                suggestion="Swap or correct the dates.",
            ))
        return errors


@dataclass
class FeatureSpec:
    """Feature / indicator definition."""

    name: str
    kind: str = "indicator"
    params: dict[str, Any] | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> FeatureSpec:
        return FeatureSpec(
            name=data["name"],
            kind=data.get("kind", "indicator"),
            params=data.get("params"),
        )


@dataclass
class EventSpec:
    """Event trigger definition."""

    name: str
    params: dict[str, Any] | None = None
    cooldown_bars: int = 0
    min_separation_bars: int = 1

    @staticmethod
    def from_dict(data: dict[str, Any]) -> EventSpec:
        return EventSpec(
            name=data["name"],
            params=data.get("params"),
            cooldown_bars=data.get("cooldown_bars", 0),
            min_separation_bars=data.get("min_separation_bars", 1),
        )

    def validate(self) -> ValidationResult:
        errors: ValidationResult = []
        if not self.name:
            errors.append(ValidationError(
                path="events[].name",
                message="Event name must not be empty",
                suggestion="Provide a name that resolves in the event registry.",
            ))
        if self.min_separation_bars < 0:
            errors.append(ValidationError(
                path="events[].min_separation_bars",
                message=f"min_separation_bars must be >= 0, got {self.min_separation_bars}",
                suggestion="Use 0 for consecutive bars or 1+ for minimum gap.",
            ))
        if self.cooldown_bars < 0:
            errors.append(ValidationError(
                path="events[].cooldown_bars",
                message=f"cooldown_bars must be >= 0, got {self.cooldown_bars}",
                suggestion="Set 0 for no cooldown or a positive integer.",
            ))
        return errors


@dataclass
class OutcomeSpec:
    """Outcome metric definition."""

    name: str
    params: dict[str, Any] | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> OutcomeSpec:
        return OutcomeSpec(
            name=data["name"],
            params=data.get("params"),
        )

    def validate(self) -> ValidationResult:
        errors: ValidationResult = []
        if not self.name:
            errors.append(ValidationError(
                path="outcomes[].name",
                message="Outcome name must not be empty",
                suggestion="Provide a name that resolves in the outcome registry.",
            ))
        return errors


@dataclass
class FilterSpec:
    """Pre/post event filter expressions."""

    pre_event: list[str] = field(default_factory=list)
    post_event: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> FilterSpec:
        return FilterSpec(
            pre_event=data.get("pre_event", []),
            post_event=data.get("post_event", []),
        )


@dataclass
class AnalysisConfidence:
    """Confidence estimation config."""

    method: str = "none"
    iterations: int = 2000
    ci: float = 0.95

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AnalysisConfidence:
        return AnalysisConfidence(
            method=data.get("method", "none"),
            iterations=data.get("iterations", 2000),
            ci=data.get("ci", 0.95),
        )

    def validate(self) -> ValidationResult:
        errors: ValidationResult = []
        if self.method not in ("none", "bootstrap"):
            errors.append(ValidationError(
                path="analysis.confidence.method",
                message=f"Unknown confidence method '{self.method}'",
                suggestion="Use 'none' or 'bootstrap'.",
            ))
        if not 0 < self.ci < 1:
            errors.append(ValidationError(
                path="analysis.confidence.ci",
                message=f"ci must be in (0, 1), got {self.ci}",
                suggestion="Use a value like 0.90, 0.95, or 0.99.",
            ))
        if self.iterations < 100:
            errors.append(ValidationError(
                path="analysis.confidence.iterations",
                message=f"iterations must be >= 100, got {self.iterations}",
                suggestion="Use at least 1000 for stable intervals.",
            ))
        return errors


@dataclass
class AnalysisStatistics:
    """Statistics config."""

    include: list[str] = field(default_factory=lambda: ["mean", "median", "std", "hit_rate"])
    quantiles: list[float] | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AnalysisStatistics:
        return AnalysisStatistics(
            include=data.get("include", ["mean", "median", "std", "hit_rate"]),
            quantiles=data.get("quantiles"),
        )

    def validate(self) -> ValidationResult:
        errors: ValidationResult = []
        if self.quantiles:
            for q in self.quantiles:
                if not 0 <= q <= 1:
                    errors.append(ValidationError(
                        path="analysis.statistics.quantiles",
                        message=f"Quantile {q} outside [0, 1]",
                        suggestion="All quantiles must be in [0, 1].",
                    ))
            if len(self.quantiles) > 1:
                for i in range(len(self.quantiles) - 1):
                    if self.quantiles[i] >= self.quantiles[i + 1]:
                        errors.append(ValidationError(
                            path="analysis.statistics.quantiles",
                            message=f"Quantiles not strictly increasing: {self.quantiles}",
                            suggestion="Sort quantiles ascending, e.g. [0.05, 0.25, 0.5, 0.75, 0.95].",
                        ))
                        break
        return errors


@dataclass
class AnalysisSpec:
    """Analysis configuration (confidence + statistics)."""

    confidence: AnalysisConfidence | None = None
    statistics: AnalysisStatistics | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> AnalysisSpec:
        return AnalysisSpec(
            confidence=AnalysisConfidence.from_dict(data.get("confidence", {}))
            if "confidence" in data else None,
            statistics=AnalysisStatistics.from_dict(data.get("statistics", {}))
            if "statistics" in data else None,
        )

    def validate(self) -> ValidationResult:
        errors: ValidationResult = []
        if self.confidence:
            errors.extend(self.confidence.validate())
        if self.statistics:
            errors.extend(self.statistics.validate())
        return errors


@dataclass
class ReportingSpec:
    """Reporting configuration."""

    output_dir: str = "artifacts"
    formats: list[str] | None = None
    charts: list[str] | None = None

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ReportingSpec:
        return ReportingSpec(
            output_dir=data.get("output_dir", "artifacts"),
            formats=data.get("formats"),
            charts=data.get("charts"),
        )

    def validate(self) -> ValidationResult:
        errors: ValidationResult = []
        valid_formats = {"csv", "json", "parquet"}
        if self.formats:
            for fmt in self.formats:
                if fmt not in valid_formats:
                    errors.append(ValidationError(
                        path="reporting.formats",
                        message=f"Unknown format '{fmt}'",
                        suggestion=f"Use one of: {', '.join(sorted(valid_formats))}.",
                    ))
        valid_charts = {"distribution", "grouped_bar", "event_timeline"}
        if self.charts:
            for chart in self.charts:
                if chart not in valid_charts:
                    errors.append(ValidationError(
                        path="reporting.charts",
                        message=f"Unknown chart '{chart}'",
                        suggestion=f"Use one of: {', '.join(sorted(valid_charts))}.",
                    ))
        return errors


@dataclass
class ExecutionSpec:
    """Execution runtime configuration."""

    seed: int = 42
    max_workers: int = 1
    cache_features: bool = True
    fail_on_warnings: bool = False

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ExecutionSpec:
        return ExecutionSpec(
            seed=data.get("seed", 42),
            max_workers=data.get("max_workers", 1),
            cache_features=data.get("cache_features", True),
            fail_on_warnings=data.get("fail_on_warnings", False),
        )

    def validate(self) -> ValidationResult:
        errors: ValidationResult = []
        if self.max_workers < 1:
            errors.append(ValidationError(
                path="execution.max_workers",
                message=f"max_workers must be >= 1, got {self.max_workers}",
                suggestion="Use 1 for single-threaded or 2+ for parallel.",
            ))
        return errors


# ---------------------------------------------------------------------------
# Top-level experiment spec
# ---------------------------------------------------------------------------
SUPPORTED_VERSIONS = {1}


@dataclass
class ExperimentSpec:
    """Complete experiment specification — mirrors the top-level YAML schema."""

    version: int
    experiment: dict[str, str]
    dataset: DatasetSpec
    features: list[FeatureSpec] = field(default_factory=list)
    events: list[EventSpec] = field(default_factory=list)
    outcomes: list[OutcomeSpec] = field(default_factory=list)
    filters: FilterSpec | None = None
    group_by: list[str] | None = None
    analysis: AnalysisSpec | None = None
    reporting: ReportingSpec | None = None
    execution: ExecutionSpec | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentSpec:
        """Construct from a parsed YAML/JSON dict.

        Applies defaults for optional sections. Does NOT validate —
        call .validate() separately.
        """
        raw_ds = data.get("dataset", {})
        raw_features = data.get("features", [])
        raw_events = data.get("events", [])
        raw_outcomes = data.get("outcomes", [])

        return cls(
            version=data.get("version", 1),
            experiment=data.get("experiment", {}),
            dataset=DatasetSpec.from_dict(raw_ds),
            features=[FeatureSpec.from_dict(f) for f in raw_features],
            events=[EventSpec.from_dict(e) for e in raw_events],
            outcomes=[OutcomeSpec.from_dict(o) for o in raw_outcomes],
            filters=FilterSpec.from_dict(data.get("filters", {}))
            if "filters" in data else None,
            group_by=data.get("group_by"),
            analysis=AnalysisSpec.from_dict(data["analysis"])
            if "analysis" in data else None,
            reporting=ReportingSpec.from_dict(data["reporting"])
            if "reporting" in data else None,
            execution=ExecutionSpec.from_dict(data["execution"])
            if "execution" in data else None,
        )

    def validate(self) -> ValidationResult:
        """Run full semantic validation. Returns list of errors (empty = valid)."""
        errors: ValidationResult = []

        # version
        if self.version not in SUPPORTED_VERSIONS:
            errors.append(ValidationError(
                path="version",
                message=f"Unsupported schema version {self.version}",
                suggestion=f"Use one of: {', '.join(str(v) for v in sorted(SUPPORTED_VERSIONS))}.",
            ))

        # experiment header
        exp_name = self.experiment.get("name", "")
        if not exp_name:
            errors.append(ValidationError(
                path="experiment.name",
                message="Experiment name is required",
                suggestion="Give your experiment a descriptive name.",
            ))
        exp_type = self.experiment.get("type", "")
        if exp_type not in ("event_study", "backtest"):
            errors.append(ValidationError(
                path="experiment.type",
                message=f"Invalid experiment type '{exp_type}'",
                suggestion="Use 'event_study' or 'backtest'.",
            ))

        # dataset
        errors.extend(self.dataset.validate())

        # events
        if not self.events:
            errors.append(ValidationError(
                path="events",
                message="At least one event is required",
                suggestion="Add an event definition, e.g. volume_spike.",
            ))
        seen_events: set[str] = set()
        for i, ev in enumerate(self.events):
            path_prefix = f"events[{i}]"
            for e in ev.validate():
                e.path = f"{path_prefix}.{e.path}"  # noqa: PLW2901
                errors.append(e)
            if ev.name:
                if ev.name in seen_events:
                    errors.append(ValidationError(
                        path=f"{path_prefix}.name",
                        message=f"Duplicate event name '{ev.name}'",
                        suggestion="Rename or remove the duplicate.",
                    ))
                seen_events.add(ev.name)

        # outcomes
        if not self.outcomes:
            errors.append(ValidationError(
                path="outcomes",
                message="At least one outcome is required",
                suggestion="Add an outcome definition, e.g. forward_return.",
            ))
        seen_outcomes: set[str] = set()
        for i, oc in enumerate(self.outcomes):
            path_prefix = f"outcomes[{i}]"
            for e in oc.validate():
                e.path = f"{path_prefix}.{e.path}"  # noqa: PLW2901
                errors.append(e)
            if oc.name:
                if oc.name in seen_outcomes:
                    errors.append(ValidationError(
                        path=f"{path_prefix}.name",
                        message=f"Duplicate outcome name '{oc.name}'",
                        suggestion="Rename or remove the duplicate.",
                    ))
                seen_outcomes.add(oc.name)

        # features — validate names are non-empty
        seen_features: set[str] = set()
        for i, feat in enumerate(self.features):
            if not feat.name:
                errors.append(ValidationError(
                    path=f"features[{i}].name",
                    message="Feature name must not be empty",
                ))
            if feat.name and feat.name in seen_features:
                errors.append(ValidationError(
                    path=f"features[{i}].name",
                    message=f"Duplicate feature name '{feat.name}'",
                    suggestion="Rename or remove the duplicate.",
                ))
            if feat.name:
                seen_features.add(feat.name)

        # analysis
        if self.analysis:
            errors.extend(self.analysis.validate())

        # reporting
        if self.reporting:
            errors.extend(self.reporting.validate())

        # execution
        if self.execution:
            errors.extend(self.execution.validate())

        return errors

    @property
    def experiment_type(self) -> str:
        return self.experiment.get("type", "event_study")

    @property
    def experiment_name(self) -> str:
        return self.experiment.get("name", "untitled")


EXPERIMENT_SPEC_SCHEMA = {
    "version": {"type": "int", "required": True},
    "experiment": {"type": "dict", "required": True},
    "dataset": {"type": "dict", "required": True},
    "events": {"type": "list", "required": True},
    "outcomes": {"type": "list", "required": True},
}
