from __future__ import annotations

import tempfile
from pathlib import Path

import polars as pl
import pytest

from ssbt.data.feed import InMemoryFeed
from ssbt.service import (
    BacktestRequest,
    DataSpec,
    ExecutionProfile,
    ExecutionSpec,
    FeedCache,
    ProfileConfig,
    StrategySpec,
    TenantContext,
    apply_execution_profile,
    run_backtest,
    run_backtest_async,
)


@pytest.fixture
def sample_df() -> pl.DataFrame:
    return pl.DataFrame({
        "timestamp": [1700000000000, 1700000060000, 1700000120000],
        "open": [100.0, 101.0, 102.0],
        "high": [105.0, 106.0, 107.0],
        "low": [99.0, 100.0, 101.0],
        "close": [104.0, 105.0, 106.0],
        "volume": [1000.0, 1200.0, 1100.0],
    })


def test_execution_profile_enum():
    assert ExecutionProfile.FAST == "fast"
    assert ExecutionProfile.BALANCED == "balanced"
    assert ExecutionProfile.MAX_FIDELITY == "max_fidelity"
    assert ExecutionProfile("fast") == ExecutionProfile.FAST


def test_profile_config_defaults():
    cfg = ProfileConfig()
    assert cfg.safe_mode is True
    assert cfg.enable_microstructure is False
    assert cfg.enable_overfitting_defense is False
    assert cfg.enable_ipc_stream is False
    assert "safe_mode" in cfg.to_dict()


def test_apply_execution_profile_fast():
    req = BacktestRequest()
    updated = apply_execution_profile(req, ExecutionProfile.FAST)
    assert updated.execution.profile == "fast"
    assert updated.execution.safe_mode is True
    assert updated.execution.enable_microstructure is False
    assert updated.execution.enable_overfitting_defense is False
    assert updated.execution.enable_ipc_stream is False


def test_apply_execution_profile_balanced_str():
    req = BacktestRequest()
    updated = apply_execution_profile(req, "balanced")
    assert updated.execution.profile == "balanced"
    assert updated.execution.safe_mode is True
    assert updated.execution.enable_microstructure is True
    assert updated.execution.impact_model == "square_root"
    assert updated.execution.enable_overfitting_defense is False
    assert updated.execution.enable_ipc_stream is False


def test_apply_execution_profile_max_fidelity():
    req = BacktestRequest()
    updated = apply_execution_profile(req, ExecutionProfile.MAX_FIDELITY)
    assert updated.execution.profile == "max_fidelity"
    assert updated.execution.safe_mode is True
    assert updated.execution.enable_microstructure is True
    assert updated.execution.enable_overfitting_defense is True
    assert updated.execution.enable_ipc_stream is True


def test_apply_execution_profile_invalid():
    req = BacktestRequest()
    with pytest.raises(ValueError, match="Invalid execution profile"):
        apply_execution_profile(req, "ultra_fast")


def test_feed_cache_warm_feed_reuse(sample_df: pl.DataFrame):
    FeedCache.clear()

    feed1 = FeedCache.get_or_load(sample_df, symbol="BTCUSDT")
    feed2 = FeedCache.get_or_load(sample_df, symbol="BTCUSDT")

    assert isinstance(feed1, InMemoryFeed)
    assert feed1 is feed2

    # Different symbol creates different entry
    feed3 = FeedCache.get_or_load(sample_df, symbol="ETHUSDT")
    assert feed3 is not feed1

    # Clear cache
    FeedCache.clear()
    feed4 = FeedCache.get_or_load(sample_df, symbol="BTCUSDT")
    assert feed4 is not feed1


def test_feed_cache_file_path(sample_df: pl.DataFrame):
    FeedCache.clear()
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        sample_df.write_parquet(tmp_path)
        feed1 = FeedCache.get_or_load(tmp_path, symbol="BTCUSDT")
        feed2 = FeedCache.get_or_load(str(tmp_path), symbol="BTCUSDT")
        assert feed1 is feed2
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_run_backtest_with_execution_profile_and_tenant_context(sample_df: pl.DataFrame):
    context = TenantContext(org_id="fintech_corp", user_id="trader_joe", project_id="alpha_strategy")
    req = BacktestRequest(
        run_id="test_profile_run_123",
        data=DataSpec(symbol="BTCUSDT", dataframe=sample_df),
        strategy=StrategySpec(name="Strategy"),
    )

    resp = run_backtest(req, context=context, profile=ExecutionProfile.BALANCED)
    assert resp.status == "success"
    assert resp.run_id == "test_profile_run_123"

    expected_dir = Path("artifacts") / "fintech_corp" / "trader_joe" / "alpha_strategy" / "test_profile_run_123"
    assert expected_dir.exists()
    assert (expected_dir / "request.json").exists()
    assert (expected_dir / "response.json").exists()


import asyncio


def test_run_backtest_async_with_profile(sample_df: pl.DataFrame):
    context = TenantContext(org_id="org_async", user_id="usr_async", project_id="prj_async")
    req = BacktestRequest(
        run_id="test_async_profile_run",
        data=DataSpec(symbol="ETHUSDT", dataframe=sample_df),
    )

    resp = asyncio.run(run_backtest_async(req, context=context, profile="max_fidelity"))
    assert resp.status == "success"
    expected_dir = Path("artifacts") / "org_async" / "usr_async" / "prj_async" / "test_async_profile_run"
    assert expected_dir.exists()
