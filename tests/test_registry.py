"""Tests for plugin registry — dispatch, duplicates, unknown, list/has, integration."""

from __future__ import annotations

import polars as pl
import pytest

from ssbt.events.base import BaseEvent
from ssbt.outcomes.base import BaseOutcome
from ssbt.experiments.registry import Registry, RegistryError


# ── Stub plugins for testing ────────────────────────────────────────────

class _StubEvent(BaseEvent):
    name = "stub_event"
    api_version = 1

    def compute_events(self, df, params):
        return pl.DataFrame({
            "event_id": [1],
            "timestamp": [100],
            "event_name": ["stub_event"],
            "symbol": [""],
            "event_meta": [{}],
        })


class _StubOutcome(BaseOutcome):
    name = "stub_outcome"
    api_version = 1

    def compute_outcomes(self, df, events, params):
        return pl.DataFrame({
            "event_id": [1],
            "outcome_name": ["stub_outcome"],
            "horizon": [1],
            "value": [0.01],
        })


class _NoComputeEvent(BaseEvent):
    name = "no_compute"
    api_version = 1
    # no compute_events — should fail registry check


class _NoComputeOutcome(BaseOutcome):
    name = "no_compute"
    api_version = 1
    # no compute_outcomes — should fail registry check


class _SecondEvent(BaseEvent):
    name = "second_event"
    api_version = 1

    def compute_events(self, df, params):
        return pl.DataFrame({
            "event_id": [1],
            "timestamp": [100],
            "event_name": ["second_event"],
            "symbol": [""],
            "event_meta": [{}],
        })


class _SecondOutcome(BaseOutcome):
    name = "second_outcome"
    api_version = 1

    def compute_outcomes(self, df, events, params):
        return pl.DataFrame({
            "event_id": [1],
            "outcome_name": ["second_outcome"],
            "horizon": [1],
            "value": [0.02],
        })


# ── Tests ───────────────────────────────────────────────────────────────

class TestRegistryEventRegistration:
    def test_register_and_get_event(self):
        reg = Registry()
        reg.register_event("stub", _StubEvent)
        cls = reg.get_event("stub")
        assert cls is _StubEvent

    def test_register_event_duplicate_raises(self):
        reg = Registry()
        reg.register_event("stub", _StubEvent)
        with pytest.raises(RegistryError, match="already registered"):
            reg.register_event("stub", _StubEvent)

    def test_register_event_with_different_class_same_name(self):
        reg = Registry()
        reg.register_event("e1", _StubEvent)
        with pytest.raises(RegistryError, match="already registered"):
            reg.register_event("e1", _SecondEvent)

    def test_register_event_empty_name(self):
        reg = Registry()
        with pytest.raises(RegistryError, match="must not be empty"):
            reg.register_event("", _StubEvent)

    def test_register_event_no_compute_method(self):
        reg = Registry()
        with pytest.raises(RegistryError, match="no concrete compute_events method"):
            reg.register_event("bad", _NoComputeEvent)

    def test_get_event_unknown_raises(self):
        reg = Registry()
        with pytest.raises(RegistryError, match="Unknown event"):
            reg.get_event("nonexistent")

    def test_get_event_unknown_includes_registered(self):
        reg = Registry()
        reg.register_event("stub", _StubEvent)
        with pytest.raises(RegistryError, match="stub"):
            reg.get_event("wrong")


class TestRegistryOutcomeRegistration:
    def test_register_and_get_outcome(self):
        reg = Registry()
        reg.register_outcome("stub", _StubOutcome)
        cls = reg.get_outcome("stub")
        assert cls is _StubOutcome

    def test_register_outcome_duplicate_raises(self):
        reg = Registry()
        reg.register_outcome("stub", _StubOutcome)
        with pytest.raises(RegistryError, match="already registered"):
            reg.register_outcome("stub", _StubOutcome)

    def test_register_outcome_empty_name(self):
        reg = Registry()
        with pytest.raises(RegistryError, match="must not be empty"):
            reg.register_outcome("", _StubOutcome)

    def test_register_outcome_no_compute_method(self):
        reg = Registry()
        with pytest.raises(RegistryError, match="no concrete compute_outcomes method"):
            reg.register_outcome("bad", _NoComputeOutcome)

    def test_get_outcome_unknown_raises(self):
        reg = Registry()
        with pytest.raises(RegistryError, match="Unknown outcome"):
            reg.get_outcome("nonexistent")

    def test_get_outcome_unknown_includes_registered(self):
        reg = Registry()
        reg.register_outcome("stub", _StubOutcome)
        with pytest.raises(RegistryError, match="stub"):
            reg.get_outcome("wrong")


class TestRegistryListing:
    def test_list_events_empty(self):
        reg = Registry()
        assert reg.list_events() == []

    def test_list_events_sorted(self):
        reg = Registry()
        reg.register_event("z_event", _SecondEvent)
        reg.register_event("a_event", _StubEvent)
        assert reg.list_events() == ["a_event", "z_event"]

    def test_list_outcomes_empty(self):
        reg = Registry()
        assert reg.list_outcomes() == []

    def test_list_outcomes_sorted(self):
        reg = Registry()
        reg.register_outcome("z_outcome", _SecondOutcome)
        reg.register_outcome("a_outcome", _StubOutcome)
        assert reg.list_outcomes() == ["a_outcome", "z_outcome"]


class TestRegistryHas:
    def test_has_event_true(self):
        reg = Registry()
        reg.register_event("stub", _StubEvent)
        assert reg.has_event("stub") is True

    def test_has_event_false(self):
        reg = Registry()
        assert reg.has_event("stub") is False

    def test_has_outcome_true(self):
        reg = Registry()
        reg.register_outcome("stub", _StubOutcome)
        assert reg.has_outcome("stub") is True

    def test_has_outcome_false(self):
        reg = Registry()
        assert reg.has_outcome("stub") is False


class TestRegistryIndependence:
    def test_events_and_outcomes_do_not_interfere(self):
        reg = Registry()
        reg.register_event("e1", _StubEvent)
        reg.register_outcome("o1", _StubOutcome)
        assert reg.has_event("e1") is True
        assert reg.has_event("o1") is False
        assert reg.has_outcome("o1") is True
        assert reg.has_outcome("e1") is False

    def test_same_name_in_both_registries(self):
        reg = Registry()
        reg.register_event("shared", _StubEvent)
        reg.register_outcome("shared", _StubOutcome)
        assert reg.has_event("shared") is True
        assert reg.has_outcome("shared") is True


class TestRegistryIntegration:
    """Full round-trip: register → get → instantiate → compute → verify."""

    def test_event_roundtrip(self):
        reg = Registry()
        reg.register_event("stub", _StubEvent)

        cls = reg.get_event("stub")
        instance = cls()

        df = pl.DataFrame({"timestamp": [1, 2, 3], "close": [10, 11, 12]})
        result = instance.compute_events(df, {})
        assert isinstance(result, pl.DataFrame)
        assert "event_id" in result.columns
        assert "timestamp" in result.columns
        assert "event_name" in result.columns

    def test_outcome_roundtrip(self):
        reg = Registry()
        reg.register_outcome("stub", _StubOutcome)

        cls = reg.get_outcome("stub")
        instance = cls()

        df = pl.DataFrame({"timestamp": [1, 2, 3], "close": [10, 11, 12]})
        events = pl.DataFrame({"event_id": [1], "timestamp": [100]})
        result = instance.compute_outcomes(df, events, {})
        assert isinstance(result, pl.DataFrame)
        assert "event_id" in result.columns
        assert "outcome_name" in result.columns
        assert "horizon" in result.columns
        assert "value" in result.columns

    def test_multiple_events_integration(self):
        """Register both events, get each, call compute."""
        reg = Registry()
        reg.register_event("stub", _StubEvent)
        reg.register_event("second", _SecondEvent)

        e1 = reg.get_event("stub")()
        e2 = reg.get_event("second")()

        df = pl.DataFrame({"timestamp": [1, 2, 3], "close": [10, 11, 12]})
        r1 = e1.compute_events(df, {})
        r2 = e2.compute_events(df, {})

        assert len(r1) == 1
        assert r1["event_name"][0] == "stub_event"
        assert len(r2) == 1
        assert r2["event_name"][0] == "second_event"

    def test_registry_isolation_two_registries(self):
        """Two registries should not share state."""
        r1 = Registry()
        r2 = Registry()
        r1.register_event("stub", _StubEvent)
        assert r2.has_event("stub") is False
