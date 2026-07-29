"""Unit tests for SSBT exception hierarchy and diagnostic hints."""

import pytest
import polars as pl
from ssbt import (
    SSBTError, DataError, ExecutionError, AuditError,
    InMemoryFeed,
)


def test_ssbt_error_formatting():
    err = SSBTError(
        message="Failed to compute volatility.",
        hint="Ensure returns array has at least 2 observations.",
        context={"len": 1},
    )
    assert err.message == "Failed to compute volatility."
    assert err.hint == "Ensure returns array has at least 2 observations."
    assert err.context == {"len": 1}
    assert "[HINT]: Ensure returns array has at least 2 observations." in str(err)


def test_data_error_raised_by_in_memory_feed():
    invalid_df = pl.DataFrame({
        "date_col": [1, 2, 3],
        "price_col": [10.0, 11.0, 12.0],
    })

    with pytest.raises(DataError) as exc_info:
        _ = InMemoryFeed(invalid_df, symbol="TEST")

    err = exc_info.value
    assert "Cannot detect valid OHLCV or Bid/Ask market data schema" in err.message
    assert "[HINT]: Ensure your Polars DataFrame has columns" in str(err)
    assert err.context["symbol"] == "TEST"


def test_execution_error_attributes():
    err = ExecutionError(
        message="Order volume exceeds ADV participation cap.",
        hint="Reduce order quantity or increase ADV liquidity cap percentage.",
        context={"order_qty": 500, "max_allowed": 100},
    )
    assert isinstance(err, SSBTError)
    assert err.context["order_qty"] == 500


def test_audit_error_attributes():
    err = AuditError(
        message="Timestamp causality violation detected in point-in-time join.",
        hint="Use align_multi_timeframe() with shift(1) to avoid lookahead leakage.",
    )
    assert isinstance(err, SSBTError)
    assert "shift(1)" in str(err)
