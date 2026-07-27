"""Tests for event plugin contract and base class."""

from __future__ import annotations

import polars as pl
import pytest

from ssbt.events.base import BaseEvent, EventTableRow, REQUIRED_EVENT_COLUMNS


# ── Stub plugin for testing ───────────────────────────────────────────
class _ValidEvent(BaseEvent):
    name = "test_event"
    api_version = 1

    def compute_events(self, df, params):
        return pl.DataFrame({
            "event_id": [1, 2],
            "timestamp": [100, 200],
            "event_name": ["test_event", "test_event"],
            "symbol": ["", ""],
            "event_meta": [{}, {}],
        })


class _NoNameEvent(BaseEvent):
    name = ""
    api_version = 1

    def compute_events(self, df, params):
        return pl.DataFrame()


class _CustomEvent(BaseEvent):
    name = "custom"
    api_version = 2

    def compute_events(self, df, params):
        return pl.DataFrame({
            "event_id": [1],
            "timestamp": [100],
            "event_name": ["custom"],
        })

    def validate_params(self, params):
        errs = []
        if "threshold" not in params:
            errs.append("Missing required param: threshold")
        return errs


# ── Tests ─────────────────────────────────────────────────────────────
class TestBaseEventContract:
    def test_can_instantiate(self):
        instance = _ValidEvent()
        assert instance.name == "test_event"
        assert instance.api_version == 1

    def test_compute_events_returns_dataframe(self):
        df = pl.DataFrame({"timestamp": [1, 2, 3], "close": [10, 11, 12]})
        result = _ValidEvent().compute_events(df, {})
        assert isinstance(result, pl.DataFrame)
        assert len(result) == 2

    def test_event_table_required_columns(self):
        """Verify the required columns are correctly defined."""
        assert "event_id" in REQUIRED_EVENT_COLUMNS
        assert "timestamp" in REQUIRED_EVENT_COLUMNS
        assert "event_name" in REQUIRED_EVENT_COLUMNS

    def test_abstract_class_cannot_instantiate(self):
        with pytest.raises(TypeError):
            BaseEvent()  # noqa: E0110

    def test_api_version_default(self):
        class ImplicitEvent(BaseEvent):
            def compute_events(self, df, params):
                return pl.DataFrame()

        assert ImplicitEvent.api_version == 1

    def test_custom_api_version(self):
        assert _CustomEvent.api_version == 2

    def test_check_event_table_valid(self):
        result = pl.DataFrame({
            "event_id": [1],
            "timestamp": [100],
            "event_name": ["test"],
            "extra_col": [0],
        })
        # Should not raise
        BaseEvent.check_event_table(result)

    def test_check_event_table_missing_columns(self):
        result = pl.DataFrame({"event_id": [1]})
        with pytest.raises(ValueError, match="missing"):
            BaseEvent.check_event_table(result)

    def test_validate_params_default_empty(self):
        instance = _ValidEvent()
        assert instance.validate_params({"anything": 1}) == []

    def test_validate_params_custom(self):
        instance = _CustomEvent()
        errs = instance.validate_params({"something": 1})
        assert len(errs) == 1
        assert "threshold" in errs[0]

    def test_validate_params_custom_ok(self):
        instance = _CustomEvent()
        errs = instance.validate_params({"threshold": 2.0})
        assert errs == []

    def test_event_table_row_dataclass(self):
        row = EventTableRow(event_id=1, timestamp=100, event_name="spike", symbol="BTC")
        assert row.event_id == 1
        assert row.symbol == "BTC"
        assert row.event_meta == {}

    def test_event_table_row_with_meta(self):
        row = EventTableRow(
            event_id=1, timestamp=100, event_name="spike",
            event_meta={"magnitude": 3.5},
        )
        assert row.event_meta["magnitude"] == 3.5
