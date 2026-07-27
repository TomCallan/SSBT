"""Base event plugin interface.

All event detection plugins must subclass BaseEvent and implement
compute_events(). The registry maps plugin names to classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import polars as pl


# ---------------------------------------------------------------------------
# Event output schema
# ---------------------------------------------------------------------------
EVENT_TABLE_SCHEMA = {
    "event_id": pl.Int64,
    "timestamp": pl.Int64,      # epoch ns
    "symbol": pl.Utf8,          # empty string for single-asset
    "event_name": pl.Utf8,
    "event_meta": pl.Object,    # dict with per-instance metadata
}

# Columns that MUST be present in the returned DataFrame
REQUIRED_EVENT_COLUMNS = {"event_id", "timestamp", "event_name"}


@dataclass
class EventTableRow:
    """Single event occurrence for structured construction."""

    event_id: int
    timestamp: int
    event_name: str
    symbol: str = ""
    event_meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class BaseEvent(ABC):
    """Abstract base for event detection plugins.

    Subclasses must define:
      - name        (class attribute, used for registry lookup)
      - api_version (class attribute, default 1)
      - compute_events()

    Example plugin::

        class VolumeSpike(BaseEvent):
            name = "volume_spike"
            api_version = 1

            def compute_events(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
                ...
    """

    name: str = ""
    api_version: int = 1

    @abstractmethod
    def compute_events(self, df: pl.DataFrame, params: dict[str, Any]) -> pl.DataFrame:
        """Detect events in the canonical OHLCV DataFrame.

        Args:
            df: Canonical OHLCV DataFrame with at least
                ``timestamp``, ``open``, ``high``, ``low``, ``close``, ``volume``.
            params: Plugin-specific parameters from the experiment config
                    (e.g. ``{"multiplier": 3.0}``).

        Returns:
            A DataFrame conforming to EVENT_TABLE_SCHEMA with at minimum
            ``event_id``, ``timestamp``, ``event_name``.
            ``event_meta`` should contain per-event metadata (e.g. spike magnitude).
            Rows should be sorted by timestamp.

        Raises:
            ValueError: If required columns are missing or params are invalid.
        """
        ...

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        """Override to provide plugin-specific parameter validation.

        Returns a list of error messages (empty = valid).
        """
        return []

    @staticmethod
    def check_event_table(result: pl.DataFrame) -> None:
        """Validate that the returned DataFrame meets the event contract."""
        cols = set(result.columns)
        missing = REQUIRED_EVENT_COLUMNS - cols
        if missing:
            raise ValueError(
                f"Event table missing required columns: {missing}. "
                f"Has: {cols}"
            )
