"""Plugin registry for events and outcomes.

Maps registered names to plugin classes. Runner uses registry to
resolve ``events[].name`` and ``outcomes[].name`` from experiment configs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ssbt.events.base import BaseEvent
    from ssbt.outcomes.base import BaseOutcome


class RegistryError(Exception):
    """Raised on registration or lookup failures."""


class Registry:
    """Name → class registry for event and outcome plugins.

    Thread-safe for read operations (single-writer assumed at init time).
    """

    def __init__(self) -> None:
        self._events: dict[str, type[BaseEvent]] = {}
        self._outcomes: dict[str, type[BaseOutcome]] = {}

    # ── Events ────────────────────────────────────────────────────────

    def register_event(self, name: str, cls: type[BaseEvent]) -> None:
        """Register an event plugin class under *name*.

        Raises:
            RegistryError: If *name* is already registered or *cls* is invalid.
        """
        if not name:
            raise RegistryError("Event name must not be empty")
        if name in self._events:
            raise RegistryError(f"Event '{name}' is already registered")
        method = getattr(cls, "compute_events", None)
        if method is None or getattr(method, "__isabstractmethod__", False):
            raise RegistryError(
                f"Class {cls.__name__} has no concrete compute_events method"
            )
        self._events[name] = cls

    def get_event(self, name: str) -> type[BaseEvent]:
        """Look up an event plugin by name.

        Raises:
            RegistryError: If *name* is not registered.
        """
        cls = self._events.get(name)
        if cls is None:
            raise RegistryError(
                f"Unknown event '{name}'. Registered: {self.list_events()}"
            )
        return cls

    def list_events(self) -> list[str]:
        """Return sorted list of registered event names."""
        return sorted(self._events)

    def has_event(self, name: str) -> bool:
        return name in self._events

    # ── Outcomes ──────────────────────────────────────────────────────

    def register_outcome(self, name: str, cls: type[BaseOutcome]) -> None:
        """Register an outcome plugin class under *name*.

        Raises:
            RegistryError: If *name* is already registered or *cls* is invalid.
        """
        if not name:
            raise RegistryError("Outcome name must not be empty")
        if name in self._outcomes:
            raise RegistryError(f"Outcome '{name}' is already registered")
        method = getattr(cls, "compute_outcomes", None)
        if method is None or getattr(method, "__isabstractmethod__", False):
            raise RegistryError(
                f"Class {cls.__name__} has no concrete compute_outcomes method"
            )
        self._outcomes[name] = cls

    def get_outcome(self, name: str) -> type[BaseOutcome]:
        """Look up an outcome plugin by name.

        Raises:
            RegistryError: If *name* is not registered.
        """
        cls = self._outcomes.get(name)
        if cls is None:
            raise RegistryError(
                f"Unknown outcome '{name}'. Registered: {self.list_outcomes()}"
            )
        return cls

    def list_outcomes(self) -> list[str]:
        """Return sorted list of registered outcome names."""
        return sorted(self._outcomes)

    def has_outcome(self, name: str) -> bool:
        return name in self._outcomes
