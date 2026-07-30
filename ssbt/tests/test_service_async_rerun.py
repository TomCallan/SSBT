from __future__ import annotations

import asyncio
from pathlib import Path
import pytest

from ssbt.quick import generate_synthetic_bars
from ssbt.service import (
    E_RUN_NOT_FOUND,
    BacktestRequest,
    DataSpec,
    ServiceError,
    StrategySpec,
    compare,
    rerun,
    run_backtest,
    run_backtest_async,
)


def test_run_backtest_async_coroutine():
    """Verify asynchronous execution of run_backtest_async coroutine."""
    bars_df = generate_synthetic_bars(n_bars=40, seed=42)
    req = BacktestRequest(
        run_id="test_async_run_001",
        data=DataSpec(symbol="SYNTH", dataframe=bars_df),
    )

    async def _test():
        return await run_backtest_async(req)

    resp = asyncio.run(_test())
    assert resp.status == "success"
    assert resp.run_id == "test_async_run_001"
    assert len(resp.config_hash) == 64
    assert resp.error is None
    assert "total_return" in resp.summary


def test_run_backtest_async_via_asyncio_run():
    """Verify run_backtest_async directly with asyncio.run."""
    bars_df = generate_synthetic_bars(n_bars=30, seed=100)
    req = BacktestRequest(
        run_id="test_async_run_002",
        data=DataSpec(symbol="SYNTH", dataframe=bars_df),
    )
    resp = asyncio.run(run_backtest_async(req))
    assert resp.status == "success"
    assert resp.run_id == "test_async_run_002"


def test_rerun_valid_artifact_dir(tmp_path):
    """Verify rerun loads saved request/response artifacts successfully."""
    run_id = "test_rerun_valid_001"
    bars_df = generate_synthetic_bars(n_bars=50, seed=42)
    req = BacktestRequest(
        run_id=run_id,
        data=DataSpec(symbol="BTC-USD", dataframe=bars_df),
    )
    resp = run_backtest(req)
    assert resp.status == "success"

    # Test loading by run_id
    payload_by_id = rerun(run_id)
    assert payload_by_id["run_id"] == run_id
    assert "request" in payload_by_id
    assert "response" in payload_by_id
    assert payload_by_id["request"]["data"]["symbol"] == "BTC-USD"
    assert payload_by_id["response"]["status"] == "success"

    # Test loading by explicit path
    art_path = Path("artifacts") / run_id
    payload_by_path = rerun(str(art_path))
    assert payload_by_path["run_id"] == run_id
    assert payload_by_path["response"]["run_id"] == run_id


def test_rerun_non_existent_run_id_raises_service_error():
    """Verify rerun raises E_RUN_NOT_FOUND when run ID or folder is missing."""
    with pytest.raises(ServiceError) as exc_info:
        rerun("non_existent_run_id_999999")
    assert exc_info.value.code == E_RUN_NOT_FOUND
    assert "not found" in exc_info.value.message.lower()


def test_compare_metric_deltas():
    """Verify compare calculates accurate metric deltas between two runs."""
    run_a = "test_compare_run_a"
    run_b = "test_compare_run_b"

    bars_df = generate_synthetic_bars(n_bars=60, seed=42)

    # Run A: Passive strategy (no trades)
    req_a = BacktestRequest(
        run_id=run_a,
        data=DataSpec(symbol="SYNTH", dataframe=bars_df),
    )
    run_backtest(req_a)

    # Run B: Active strategy that places orders
    strat_code = """
from ssbt import Strategy, Side

class ActiveStrategy(Strategy):
    def on_bar(self, bar, engine):
        if engine.portfolio.cash > 1000:
            order = Strategy.market_order(bar.symbol, Side.BUY, 0.01)
            engine.submit_order(order)
"""
    req_b = BacktestRequest(
        run_id=run_b,
        data=DataSpec(symbol="SYNTH", dataframe=bars_df),
        strategy=StrategySpec(name="ActiveStrategy", code=strat_code),
    )
    run_backtest(req_b)

    comp = compare(run_a, run_b)

    assert comp["run_id_a"] == run_a
    assert comp["run_id_b"] == run_b

    metrics_a = comp["metrics_a"]
    metrics_b = comp["metrics_b"]
    deltas = comp["deltas"]

    # Verify deltas match exact differences
    assert deltas["total_return"] == pytest.approx(metrics_b["total_return"] - metrics_a["total_return"])
    assert deltas["sharpe"] == pytest.approx(metrics_b["sharpe"] - metrics_a["sharpe"])
    assert deltas["max_drawdown"] == pytest.approx(metrics_b["max_drawdown"] - metrics_a["max_drawdown"])
    assert deltas["n_fills"] == metrics_b["n_fills"] - metrics_a["n_fills"]
    assert deltas["n_trades"] == metrics_b["n_trades"] - metrics_a["n_trades"]
