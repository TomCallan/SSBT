"""Structured exception hierarchy with actionable diagnostic hints for SSBT Quantitative Engine."""

from __future__ import annotations
from typing import Any


class SSBTError(Exception):
    """Base exception for all SSBT engine errors with diagnostic resolution hints."""

    def __init__(
        self,
        message: str,
        hint: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        self.message = message
        self.hint = hint
        self.context = context or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        msg = self.message
        if self.hint:
            msg += f"\n  [HINT]: {self.hint}"
        return msg


class DataError(SSBTError):
    """Raised when market data ingestion, timestamp alignment, or schema validation fails."""
    pass


class ExecutionError(SSBTError):
    """Raised when order submission, matching engine logic, or risk controls encounter failures."""
    pass


class AuditError(SSBTError):
    """Raised when anti-lookahead causality checks, integrity hashing, or reproducibility assertions fail."""
    pass
