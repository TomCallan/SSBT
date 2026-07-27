"""Tests for outcome plugin contract and base class."""

from __future__ import annotations

import polars as pl
import pytest

from ssbt.outcomes.base import BaseOutcome, OutcomeRow, REQUIRED_OUTCOME_COLUMNS


# ── Stub plugin for testing ───────────────────────────────────────────
class _ValidOutcome(BaseOutcome):
    name = "test_outcome"
    api_version = 1

    def compute_outcomes(self, df, events, params):
        return pl.DataFrame({
            "event_id": [1, 1],
            "outcome_name": ["test_outcome", "test_outcome"],
            "horizon": [1, 5],
            "value": [0.01, 0.05],
        })


class _CustomOutcome(BaseOutcome):
    name = "custom"
    api_version = 2

    def compute_outcomes(self, df, events, params):
        horizons = params.get("horizons", [1])
        rows = []
        for h in horizons:
            rows.append({"event_id": 1, "outcome_name": "custom",
                         "horizon": h, "value": float(h * 0.01)})
        return pl.DataFrame(rows)

    def validate_params(self, params):
        errs = []
        if "horizons" not in params:
            errs.append("Missing required param: horizons")
        return errs


# ── Tests ─────────────────────────────────────────────────────────────
class TestBaseOutcomeContract:
    def test_can_instantiate(self):
        instance = _ValidOutcome()
        assert instance.name == "test_outcome"
        assert instance.api_version == 1

    def test_compute_outcomes_returns_dataframe(self):
        df = pl.DataFrame({"timestamp": [1, 2, 3], "close": [10, 11, 12]})
        events = pl.DataFrame({"event_id": [1], "timestamp": [1], "event_name": ["spike"]})
        result = _ValidOutcome().compute_outcomes(df, events, {})
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 2

    def test_outcome_table_required_columns(self):
        assert "event_id" in REQUIRED_OUTCOME_COLUMNS
        assert "outcome_name" in REQUIRED_OUTCOME_COLUMNS
        assert "horizon" in REQUIRED_OUTCOME_COLUMNS
        assert "value" in REQUIRED_OUTCOME_COLUMNS

    def test_abstract_class_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseOutcome()  # noqa: E0110

    def test_api_version_default(self):
        class ImplicitOutcome(BaseOutcome):
            def compute_outcomes(self, df, events, params):
                return pl.DataFrame()

        assert ImplicitOutcome.api_version == 1

    def test_custom_api_version(self):
        assert _CustomOutcome.api_version == 2

    def test_check_outcome_table_valid(self):
        result = pl.DataFrame({
            "event_id": [1],
            "outcome_name": ["test"],
            "horizon": [5],
            "value": [0.02],
            "diagnostics": [None],
        })
        BaseOutcome.check_outcome_table(result)

    def test_check_outcome_table_missing_columns(self):
        result = pl.DataFrame({"event_id": [1], "value": [0.0]})
        with pytest.raises(ValueError, match="missing"):
            BaseOutcome.check_outcome_table(result)

    def test_validate_params_default_empty(self):
        instance = _ValidOutcome()
        assert instance.validate_params({"anything": 1}) == []

    def test_validate_params_custom(self):
        instance = _CustomOutcome()
        errs = instance.validate_params({"threshold": 2.0})
        assert len(errs) == 1
        assert "horizons" in errs[0]

    def test_validate_params_custom_ok(self):
        instance = _CustomOutcome()
        errs = instance.validate_params({"horizons": [1, 5, 20]})
        assert errs == []

    def test_outcome_row_dataclass(self):
        row = OutcomeRow(event_id=1, outcome_name="ret", horizon=5, value=0.02)
        assert row.horizon == 5
        assert row.diagnostics is None

    def test_outcome_row_with_diagnostics(self):
        row = OutcomeRow(
            event_id=1, outcome_name="ret", horizon=20, value=0.0,
            diagnostics={"insufficient_future_bars": 3},
        )
        assert row.diagnostics["insufficient_future_bars"] == 3

    def test_multi_horizon_outcomes(self):
        """CustomOutcome returns one row per horizon."""
        df = pl.DataFrame({"timestamp": [1, 2, 3], "close": [10, 11, 12]})
        events = pl.DataFrame({"event_id": [1], "timestamp": [1], "event_name": ["spike"]})
        result = _CustomOutcome().compute_outcomes(df, events, {"horizons": [1, 5, 20]})
        assert len(result) == 3
        assert sorted(result["horizon"].to_list()) == [1, 5, 20]
