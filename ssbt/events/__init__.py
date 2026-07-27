"""Event detection plugins for the exploration engine."""

from ssbt.events.base import BaseEvent, EventTableRow, REQUIRED_EVENT_COLUMNS
from ssbt.events.volume_spike import VolumeSpike

__all__ = [
    "BaseEvent",
    "EventTableRow",
    "REQUIRED_EVENT_COLUMNS",
    "VolumeSpike",
]