"""Tests for experiment spec models and validation."""

from __future__ import annotations

import pytest

from ssbt.experiments.specs import (
    AnalysisConfidence,
    AnalysisSpec,
    AnalysisStatistics,
    DatasetSpec,
    EventSpec,
    ExecutionSpec,
    ExperimentSpec,
    FeatureSpec,
    FilterSpec,
    OutcomeSpec,
    ReportingSpec,
    ValidationError,
)


# ---------------------------------------------------------------------------
# DatasetSpec
# ---------------------------------------------------------------------------
class TestDatasetSpec:
    def test_minimal(self):
        ds = DatasetSpec(source="data.parquet", symbol="BTC", timeframe="1h")
        assert ds.source == "data.parquet"
        assert ds.symbol == "BTC"
        assert ds.timezone == "UTC"

    def test_from_dict(self):
        ds = DatasetSpec.from_dict({
            "source": "data.parquet",
            "symbol": "ETH",
            "timeframe": "1m",
            "start": "2024-01-01",
            "end": "2024-06-01",
            "timezone": "America/New_York",
        })
        assert ds.source == "data.parquet"
        assert ds.symbol == "ETH"
        assert ds.timezone == "America/New_York"
        assert ds.start == "2024-01-01"

    def test_from_dict_applies_defaults(self):
        ds = DatasetSpec.from_dict({"source": "x.parquet", "symbol": "A", "timeframe": "1h"})
        assert ds.timezone == "UTC"
        assert ds.start is None
        assert ds.end is None

    def test_validate_empty_source(self):
        ds = DatasetSpec(source="", symbol="A", timeframe="1h")
        errors = ds.validate()
        assert len(errors) == 1
        assert "dataset.source" in errors[0].path

    def test_validate_dates_order(self):
        ds = DatasetSpec(source="x.parquet", symbol="A", timeframe="1h",
                         start="2024-06-01", end="2024-01-01")
        errors = ds.validate()
        assert any("start" in e.path for e in errors)

    def test_validate_ok(self):
        ds = DatasetSpec(source="x.parquet", symbol="A", timeframe="1h",
                         start="2024-01-01", end="2024-06-01")
        assert ds.validate() == []


# ---------------------------------------------------------------------------
# EventSpec
# ---------------------------------------------------------------------------
class TestEventSpec:
    def test_minimal(self):
        ev = EventSpec(name="volume_spike")
        assert ev.name == "volume_spike"
        assert ev.cooldown_bars == 0

    def test_from_dict_with_params(self):
        ev = EventSpec.from_dict({
            "name": "volume_spike",
            "params": {"multiplier": 3.0},
            "cooldown_bars": 5,
            "min_separation_bars": 2,
        })
        assert ev.name == "volume_spike"
        assert ev.params["multiplier"] == 3.0
        assert ev.cooldown_bars == 5

    def test_empty_name(self):
        ev = EventSpec(name="")
        errors = ev.validate()
        assert any("empty" in e.message.lower() for e in errors)

    def test_negative_cooldown(self):
        ev = EventSpec(name="spike", cooldown_bars=-1)
        errors = ev.validate()
        assert any("cooldown_bars" in e.path for e in errors)

    def test_negative_min_separation(self):
        ev = EventSpec(name="spike", min_separation_bars=-1)
        errors = ev.validate()
        assert any("min_separation_bars" in e.path for e in errors)

    def test_validate_ok(self):
        ev = EventSpec(name="spike")
        assert ev.validate() == []


# ---------------------------------------------------------------------------
# OutcomeSpec
# ---------------------------------------------------------------------------
class TestOutcomeSpec:
    def test_minimal(self):
        oc = OutcomeSpec(name="forward_return")
        assert oc.name == "forward_return"

    def test_empty_name(self):
        oc = OutcomeSpec(name="")
        errors = oc.validate()
        assert any("empty" in e.message.lower() for e in errors)

    def test_validate_ok(self):
        oc = OutcomeSpec(name="forward_return")
        assert oc.validate() == []


# ---------------------------------------------------------------------------
# FeatureSpec
# ---------------------------------------------------------------------------
class TestFeatureSpec:
    def test_minimal(self):
        feat = FeatureSpec(name="vol_sma")
        assert feat.kind == "indicator"

    def test_from_dict(self):
        feat = FeatureSpec.from_dict({
            "name": "atr",
            "kind": "indicator",
            "params": {"window": 14},
        })
        assert feat.name == "atr"
        assert feat.params["window"] == 14


# ---------------------------------------------------------------------------
# FilterSpec
# ---------------------------------------------------------------------------
class TestFilterSpec:
    def test_defaults(self):
        fs = FilterSpec()
        assert fs.pre_event == []
        assert fs.post_event == []

    def test_from_dict(self):
        fs = FilterSpec.from_dict({
            "pre_event": ["volume > 1000"],
        })
        assert fs.pre_event == ["volume > 1000"]


# ---------------------------------------------------------------------------
# AnalysisConfidence
# ---------------------------------------------------------------------------
class TestAnalysisConfidence:
    def test_defaults(self):
        ac = AnalysisConfidence()
        assert ac.method == "none"
        assert ac.ci == 0.95

    def test_invalid_method(self):
        ac = AnalysisConfidence(method="bayesian")
        errors = ac.validate()
        assert any("method" in e.path for e in errors)

    def test_ci_out_of_range(self):
        ac = AnalysisConfidence(ci=1.5)
        errors = ac.validate()
        assert any("ci" in e.path for e in errors)

    def test_iterations_too_low(self):
        ac = AnalysisConfidence(iterations=50)
        errors = ac.validate()
        assert any("iterations" in e.path for e in errors)

    def test_validate_ok(self):
        ac = AnalysisConfidence(method="bootstrap", iterations=2000, ci=0.95)
        assert ac.validate() == []


# ---------------------------------------------------------------------------
# AnalysisStatistics
# ---------------------------------------------------------------------------
class TestAnalysisStatistics:
    def test_default_include(self):
        astat = AnalysisStatistics()
        assert "mean" in astat.include

    def test_quantile_out_of_range(self):
        astat = AnalysisStatistics(quantiles=[0.5, 1.5])
        errors = astat.validate()
        assert len(errors) >= 1

    def test_quantiles_not_increasing(self):
        astat = AnalysisStatistics(quantiles=[0.5, 0.25, 0.75])
        errors = astat.validate()
        assert len(errors) >= 1

    def test_validate_ok(self):
        astat = AnalysisStatistics(
            include=["mean", "std"],
            quantiles=[0.05, 0.25, 0.5, 0.75, 0.95],
        )
        assert astat.validate() == []


# ---------------------------------------------------------------------------
# ReportingSpec
# ---------------------------------------------------------------------------
class TestReportingSpec:
    def test_default_output_dir(self):
        rs = ReportingSpec()
        assert rs.output_dir == "artifacts"

    def test_invalid_format(self):
        rs = ReportingSpec(formats=["html"])
        errors = rs.validate()
        assert any("html" in str(e) for e in errors)

    def test_invalid_chart(self):
        rs = ReportingSpec(charts=["pie_chart"])
        errors = rs.validate()
        assert any("pie_chart" in str(e) for e in errors)

    def test_validate_ok(self):
        rs = ReportingSpec(formats=["csv", "json"], charts=["distribution"])
        assert rs.validate() == []


# ---------------------------------------------------------------------------
# ExecutionSpec
# ---------------------------------------------------------------------------
class TestExecutionSpec:
    def test_default_seed(self):
        es = ExecutionSpec()
        assert es.seed == 42

    def test_max_workers_below_one(self):
        es = ExecutionSpec(max_workers=0)
        errors = es.validate()
        assert any("max_workers" in e.path for e in errors)

    def test_validate_ok(self):
        es = ExecutionSpec(seed=7, max_workers=4)
        assert es.validate() == []


# ---------------------------------------------------------------------------
# ExperimentSpec — integration
# ---------------------------------------------------------------------------
class TestExperimentSpec:
    def test_minimal_valid(self):
        """Minimal valid experiment spec."""
        spec = ExperimentSpec(
            version=1,
            experiment={"name": "test", "type": "event_study"},
            dataset=DatasetSpec(source="data.parquet", symbol="BTC", timeframe="1h"),
            events=[EventSpec(name="spike")],
            outcomes=[OutcomeSpec(name="forward_return")],
        )
        errors = spec.validate()
        assert errors == [], f"Unexpected errors: {errors}"

    def test_missing_experiment_name(self):
        spec = ExperimentSpec(
            version=1,
            experiment={"type": "event_study"},
            dataset=DatasetSpec(source="data.parquet", symbol="BTC", timeframe="1h"),
            events=[EventSpec(name="spike")],
            outcomes=[OutcomeSpec(name="forward_return")],
        )
        errors = spec.validate()
        assert any("experiment.name" in e.path for e in errors)

    def test_invalid_experiment_type(self):
        spec = ExperimentSpec(
            version=1,
            experiment={"name": "t", "type": "regression"},
            dataset=DatasetSpec(source="data.parquet", symbol="BTC", timeframe="1h"),
            events=[EventSpec(name="spike")],
            outcomes=[OutcomeSpec(name="forward_return")],
        )
        errors = spec.validate()
        assert any("experiment.type" in e.path for e in errors)

    def test_missing_events(self):
        spec = ExperimentSpec(
            version=1,
            experiment={"name": "t", "type": "event_study"},
            dataset=DatasetSpec(source="data.parquet", symbol="BTC", timeframe="1h"),
            events=[],
            outcomes=[OutcomeSpec(name="forward_return")],
        )
        errors = spec.validate()
        assert any("events" in e.path for e in errors)

    def test_missing_outcomes(self):
        spec = ExperimentSpec(
            version=1,
            experiment={"name": "t", "type": "event_study"},
            dataset=DatasetSpec(source="data.parquet", symbol="BTC", timeframe="1h"),
            events=[EventSpec(name="spike")],
            outcomes=[],
        )
        errors = spec.validate()
        assert any("outcomes" in e.path for e in errors)

    def test_duplicate_event_names(self):
        spec = ExperimentSpec(
            version=1,
            experiment={"name": "t", "type": "event_study"},
            dataset=DatasetSpec(source="data.parquet", symbol="BTC", timeframe="1h"),
            events=[EventSpec(name="spike"), EventSpec(name="spike")],
            outcomes=[OutcomeSpec(name="forward_return")],
        )
        errors = spec.validate()
        assert any("Duplicate" in e.message for e in errors)

    def test_unsupported_version(self):
        spec = ExperimentSpec(
            version=99,
            experiment={"name": "t", "type": "event_study"},
            dataset=DatasetSpec(source="data.parquet", symbol="BTC", timeframe="1h"),
            events=[EventSpec(name="spike")],
            outcomes=[OutcomeSpec(name="forward_return")],
        )
        errors = spec.validate()
        assert any("version" in e.path for e in errors)

    def test_from_dict_full(self):
        """Build from a dict matching the YAML spec structure."""
        data = {
            "version": 1,
            "experiment": {
                "name": "volume_spike_vs_price_move",
                "type": "event_study",
                "description": "Test",
            },
            "dataset": {
                "source": "data.parquet",
                "symbol": "BTC",
                "timeframe": "1m",
                "start": "2024-01-01",
                "end": "2024-12-31",
            },
            "features": [
                {"name": "vol_sma", "kind": "indicator", "params": {"window": 50}},
            ],
            "events": [
                {"name": "volume_spike", "params": {"multiplier": 3.0}, "cooldown_bars": 3},
            ],
            "outcomes": [
                {"name": "forward_return", "params": {"horizons": [1, 5, 20]}},
            ],
            "filters": {
                "pre_event": ["atr > 0.5"],
            },
            "group_by": ["hour"],
            "analysis": {
                "confidence": {"method": "bootstrap", "iterations": 2000, "ci": 0.95},
                "statistics": {
                    "include": ["mean", "median", "hit_rate"],
                    "quantiles": [0.05, 0.25, 0.5, 0.75, 0.95],
                },
            },
            "reporting": {
                "output_dir": "artifacts/test",
                "formats": ["csv", "json"],
                "charts": ["distribution"],
            },
            "execution": {
                "seed": 42,
                "max_workers": 4,
                "cache_features": True,
            },
        }
        spec = ExperimentSpec.from_dict(data)
        errors = spec.validate()
        assert errors == [], f"Unexpected errors: {errors}"
        assert spec.experiment_name == "volume_spike_vs_price_move"
        assert spec.experiment_type == "event_study"
        assert len(spec.features) == 1
        assert len(spec.events) == 1
        assert len(spec.outcomes) == 1
        assert spec.group_by == ["hour"]
        assert spec.analysis is not None
        assert spec.analysis.confidence is not None
        assert spec.analysis.confidence.method == "bootstrap"
        assert spec.reporting is not None
        assert spec.reporting.output_dir == "artifacts/test"
        assert spec.execution is not None
        assert spec.execution.seed == 42

    def test_from_dict_minimal(self):
        """from_dict with only required fields — optional sections left as None."""
        data = {
            "version": 1,
            "experiment": {"name": "minimal", "type": "event_study"},
            "dataset": {"source": "x.parquet", "symbol": "A", "timeframe": "1h"},
            "events": [{"name": "spike"}],
            "outcomes": [{"name": "ret"}],
        }
        spec = ExperimentSpec.from_dict(data)
        errors = spec.validate()
        assert errors == [], f"Unexpected errors: {errors}"
        assert spec.features == []
        assert spec.filters is None
        assert spec.group_by is None
        assert spec.analysis is None
        assert spec.reporting is None
        assert spec.execution is None  # optional sections omitted → None

    def test_validation_errors_have_suggestions(self):
        """Check that validation errors include actionable suggestions."""
        spec = ExperimentSpec(
            version=1,
            experiment={"name": "t", "type": "event_study"},
            dataset=DatasetSpec(source="", symbol="", timeframe=""),
            events=[EventSpec(name="", cooldown_bars=-1)],
            outcomes=[OutcomeSpec(name="")],
        )
        errors = spec.validate()
        assert len(errors) > 0
        for e in errors:
            assert e.message, f"Error at {e.path} has no message"
            if e.suggestion:
                assert len(e.suggestion) > 5
