"""Unit and integration tests for BacktestAdapter."""

import numpy as np
import pytest
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.data.feed import ParquetFeed
from ssbt.tests.conftest import _SmaCrossStrategy


def test_backtest_adapter_run(single_symbol_data_path):
    strategy = _SmaCrossStrategy(fast_period=10, slow_period=30, qty=100.0)
    feed = ParquetFeed(str(single_symbol_data_path), symbol="SYNTH")
    adapter = BacktestAdapter(initial_cash=100_000.0)

    res = adapter.run_backtest(feed, strategy)

    assert "initial_cash" in res
    assert res["initial_cash"] == 100_000.0
    assert "final_equity" in res
    assert "metrics" in res
    assert "sharpe" in res["metrics"]
    assert "trades" in res
    assert res["trades"].height >= 0
    assert len(res["equity_curve"]) == 5000
