"""Base outcome plugin interface.

All outcome computation plugins must subclass BaseOutcome and implement
compute_outcomes(). The registry maps plugin names to classes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import polars as pl


# ---------------------------------------------------------------------------
# Outcome output schema
# ---------------------------------------------------------------------------
OUTCOME_TABLE_SCHEMA = {
    "event_id": pl.Int64,
    "outcome_name": pl.Utf8,
    "horizon": pl.Int64,      # bars forward
    "value": pl.Float64,
    "diagnostics": pl.Object,  # dict, e.g. {"insufficient_future_bars": 5}
}

REQUIRED_OUTCOME_COLUMNS = {"event_id", "outcome_name", "horizon", "value"}


@dataclass
class OutcomeRow:
    """Single outcome measurement for structured construction."""

    event_id: int
    outcome_name: str
    horizon: int
    value: float
    diagnostics: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------
class BaseOutcome(ABC):
    """Abstract base for outcome computation plugins.

    Subclasses must define:
      - name        (class attribute, used for registry lookup)
      - api_version (class attribute, default 1)
      - compute_outcomes()

    Example plugin::

        class ForwardReturn(BaseOutcome):
            name = "forward_return"
            api_version = 1

            def compute_outcomes(
                self, df: pl.DataFrame, events: pl.DataFrame, params: dict[str, Any]
            ) -> pl.DataFrame:
                ...
    """

    name: str = ""
    api_version: int = 1

    @abstractmethod
    def compute_outcomes(
        self,
        df: pl.DataFrame,
        events: pl.DataFrame,
        params: dict[str, Any],
    ) -> pl.DataFrame:
        """Compute outcome metrics for each event occurrence.

        Args:
            df: Canonical OHLCV DataFrame with at least
                ``timestamp``, ``open``, ``high``, ``low``, ``close``, ``volume``.
            events: Event table produced by an event plugin, with at minimum
                    ``event_id``, ``timestamp``, ``event_name``.
            params: Plugin-specific parameters (e.g. ``{"horizons": [1, 5, 20]}``).

        Returns:
            A DataFrame conforming to OUTCOME_TABLE_SCHEMA with at minimum
            ``event_id``, ``outcome_name``, ``horizon``, ``value``.
            One row per (event_id, horizon) combination.
            Should include diagnostic info for edge cases (e.g. event too close
            to end of data for the requested horizon).

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
    def check_outcome_table(result: pl.DataFrame) -> None:
        """Validate that the returned DataFrame meets the outcome contract."""
        cols = set(result.columns)
        missing = REQUIRED_OUTCOME_COLUMNS - cols
        if missing:
            raise ValueError(
                f"Outcome table missing required columns: {missing}. "
                f"Has: {cols}"
            )
