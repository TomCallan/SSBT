"""Structured exception hierarchy for SSBT Quantitative Exploration & Backtesting Engine."""

from __future__ import annotations


class SSBTError(Exception):
    """Base exception for all SSBT engine errors."""
    pass


class DataError(SSBTError):
    """Raised when market data ingestion, timestamp alignment, or schema validation fails."""
    pass


class ExecutionError(SSBTError):
    """Raised when order submission, matching engine logic, or risk controls encounter failures."""
    pass


class AuditError(SSBTError):
    """Raised when anti-lookahead causality checks, integrity hashing, or reproducibility assertions fail."""
    pass
