from pathlib import Path
import polars as pl
import pytest

from ssbt.quick import generate_synthetic_bars
from ssbt.service import (
    E_DATA_SCHEMA,
    E_RESOURCE_LIMIT,
    E_STRATEGY_INIT,
    BacktestRequest,
    DataSpec,
    ResourceLimitSpec,
    StrategySpec,
    _compute_config_hash,
    run_backtest,
)


def test_compute_config_hash_consistency():
    req1 = BacktestRequest(data=DataSpec(symbol="BTC-USD"))
    req2 = BacktestRequest(data=DataSpec(symbol="BTC-USD"))
    hash1 = _compute_config_hash(req1)
    hash2 = _compute_config_hash(req2)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_run_backtest_success_with_synthetic_dataframe(tmp_path):
    bars_df = generate_synthetic_bars(n_bars=50, seed=42)
    strat_code = """
from ssbt import Strategy, Side

class BuyEveryBarStrategy(Strategy):
    def on_bar(self, bar, engine):
        if engine.portfolio.cash > 1000:
            order = Strategy.market_order(bar.symbol, Side.BUY, 0.01)
            engine.submit_order(order)
"""
    req = BacktestRequest(
        run_id="test_run_success_001",
        data=DataSpec(symbol="SYNTH", dataframe=bars_df),
        strategy=StrategySpec(name="BuyEveryBarStrategy", code=strat_code),
    )

    resp = run_backtest(req)
    assert resp.status == "success"
    assert resp.run_id == "test_run_success_001"
    assert len(resp.config_hash) == 64
    assert resp.error is None
    assert "total_return" in resp.summary
    assert len(resp.equity_curve) > 0

    # Verify artifacts created
    art_dir = Path("artifacts/test_run_success_001")
    assert art_dir.exists()
    assert (art_dir / "request.json").exists()
    assert (art_dir / "response.json").exists()


def test_run_backtest_timestamp_datetime_conversion():
    bars_df = generate_synthetic_bars(n_bars=20, seed=123)
    # Convert timestamp column to datetime
    bars_df = bars_df.with_columns(pl.from_epoch(pl.col("timestamp"), time_unit="ms"))

    req = BacktestRequest(
        run_id="test_run_dt_conv",
        data=DataSpec(symbol="ETH-USD", dataframe=bars_df),
    )
    resp = run_backtest(req)
    assert resp.status == "success", f"Failed with error: {resp.error}"
    assert resp.audit["symbol"] == "ETH-USD"


def test_run_backtest_missing_data_error():
    req = BacktestRequest(
        data=DataSpec(symbol="BTC-USD", dataframe=None, parquet_path=None)
    )
    resp = run_backtest(req)
    assert resp.status == "failed"
    assert resp.error is not None
    assert resp.error.code == E_DATA_SCHEMA
    assert "missing" in resp.error.message.lower()


def test_run_backtest_empty_data_error():
    empty_df = pl.DataFrame()
    req = BacktestRequest(
        data=DataSpec(symbol="BTC-USD", dataframe=empty_df)
    )
    resp = run_backtest(req)
    assert resp.status == "failed"
    assert resp.error is not None
    assert resp.error.code == E_DATA_SCHEMA


def test_run_backtest_invalid_schema_error():
    bad_df = pl.DataFrame({"invalid_col": [1, 2, 3]})
    req = BacktestRequest(
        data=DataSpec(symbol="BTC-USD", dataframe=bad_df)
    )
    resp = run_backtest(req)
    assert resp.status == "failed"
    assert resp.error is not None
    assert resp.error.code == E_DATA_SCHEMA


def test_run_backtest_strategy_compilation_syntax_error():
    bars_df = generate_synthetic_bars(n_bars=20)
    broken_code = "class BrokenStrategy(Strategy:\n    def on_bar(self): pass"
    req = BacktestRequest(
        data=DataSpec(dataframe=bars_df),
        strategy=StrategySpec(code=broken_code),
    )
    resp = run_backtest(req)
    assert resp.status == "failed"
    assert resp.error is not None
    assert resp.error.code == E_STRATEGY_INIT


def test_run_backtest_strategy_missing_subclass_error():
    bars_df = generate_synthetic_bars(n_bars=20)
    no_subclass_code = "class PlainClass:\n    pass"
    req = BacktestRequest(
        data=DataSpec(dataframe=bars_df),
        strategy=StrategySpec(code=no_subclass_code),
    )
    resp = run_backtest(req)
    assert resp.status == "failed"
    assert resp.error is not None
    assert resp.error.code == E_STRATEGY_INIT


def test_run_backtest_bar_limit_error():
    bars_df = generate_synthetic_bars(n_bars=100)
    req = BacktestRequest(
        data=DataSpec(dataframe=bars_df),
        limits=ResourceLimitSpec(max_bars=50),
    )
    resp = run_backtest(req)
    assert resp.status == "failed"
    assert resp.error is not None
    assert resp.error.code == E_RESOURCE_LIMIT
    assert "exceeds" in resp.error.message.lower()
