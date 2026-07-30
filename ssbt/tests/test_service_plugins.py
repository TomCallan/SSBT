"""Unit and integration tests for SSBT Strategy Plugin Architecture & Dry-Run Engine."""

from __future__ import annotations

import polars as pl
import pytest

import ssbt
from ssbt.quick import generate_synthetic_bars
from ssbt.service.plugins import (
    PluginManifest,
    check_plugin_compatibility,
    dry_run_strategy,
)
from ssbt.service.schemas import StrategySpec


def test_plugin_manifest_dataclass():
    manifest = PluginManifest(name="alpha_plugin", version="1.2.0")
    assert manifest.name == "alpha_plugin"
    assert manifest.version == "1.2.0"
    assert manifest.min_ssbt_version == "0.1.0"
    assert manifest.entrypoint == "main"

    d = manifest.to_dict()
    assert d == {
        "name": "alpha_plugin",
        "version": "1.2.0",
        "min_ssbt_version": "0.1.0",
        "entrypoint": "main",
    }


def test_check_plugin_compatibility_compatible():
    manifest = PluginManifest(name="test_plugin", version="1.0.0", min_ssbt_version="0.1.0")
    res = check_plugin_compatibility(manifest)
    assert res["compatible"] is True
    assert res["plugin_name"] == "test_plugin"
    assert res["plugin_version"] == "1.0.0"
    assert res["min_ssbt_version"] == "0.1.0"
    assert res["current_ssbt_version"] == ssbt.__version__
    assert res["error"] is None


def test_check_plugin_compatibility_incompatible():
    manifest = PluginManifest(name="future_plugin", version="2.0.0", min_ssbt_version="99.0.0")
    res = check_plugin_compatibility(manifest)
    assert res["compatible"] is False
    assert res["plugin_name"] == "future_plugin"
    assert res["error"] is not None
    assert "lower than required" in res["error"]


def test_check_plugin_compatibility_invalid_version():
    manifest = PluginManifest(name="broken_plugin", version="1.0.0", min_ssbt_version="not-a-version")
    res = check_plugin_compatibility(manifest)
    assert res["compatible"] is False
    assert res["error"] is not None


def test_dry_run_strategy_synthetic_data_default_strategy():
    spec = StrategySpec()
    res = dry_run_strategy(spec)
    assert res["dry_run_passed"] is True
    assert res["bars_processed"] == 5
    assert res["orders_submitted"] == 0
    assert res["fills_count"] == 0
    assert res["error"] is None


def test_dry_run_strategy_with_order_placing_strategy():
    code = """
class BuyEveryBarStrategy(Strategy):
    def on_bar(self, bar, engine):
        order = Order(id=0, symbol=bar.symbol, side=Side.BUY, type=OrderType.MARKET, qty=10.0)
        engine.submit_order(order)
"""
    spec = StrategySpec(name="BuyEveryBarStrategy", code=code)
    res = dry_run_strategy(spec)
    assert res["dry_run_passed"] is True
    assert res["strategy_name"] == "BuyEveryBarStrategy"
    assert res["bars_processed"] == 5
    assert res["orders_submitted"] > 0
    assert res["error"] is None


def test_dry_run_strategy_with_custom_dataframe_sample():
    df_sample = generate_synthetic_bars(n_bars=20, seed=123)
    spec = StrategySpec()
    res = dry_run_strategy(spec, data_sample=df_sample, symbol="CUSTOM_SYM")
    assert res["dry_run_passed"] is True
    assert res["bars_processed"] == 5


def test_dry_run_strategy_with_datetime_timestamp_dataframe():
    df = pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=pl.datetime(2026, 1, 1),
            end=pl.datetime(2026, 1, 1, 0, 10),
            interval="1m",
            eager=True,
        ),
        "open": [100.0] * 11,
        "high": [105.0] * 11,
        "low": [99.0] * 11,
        "close": [102.0] * 11,
        "volume": [1000.0] * 11,
    })
    spec = StrategySpec()
    res = dry_run_strategy(spec, data_sample=df)
    assert res["dry_run_passed"] is True
    assert res["bars_processed"] == 5


def test_dry_run_strategy_compilation_failure():
    bad_spec = StrategySpec(name="BadStrategy", code="def broken_syntax(...")
    res = dry_run_strategy(bad_spec)
    assert res["dry_run_passed"] is False
    assert res["bars_processed"] == 0
    assert res["orders_submitted"] == 0
    assert res["fills_count"] == 0
    assert res["error"] is not None


def test_dry_run_strategy_runtime_exception():
    crash_code = """
class CrashStrategy(Strategy):
    def on_bar(self, bar, engine):
        raise RuntimeError("Strategy explicit crash test")
"""
    spec = StrategySpec(name="CrashStrategy", code=crash_code)
    res = dry_run_strategy(spec)
    assert res["dry_run_passed"] is False
    assert res["error"] is not None
    assert "Strategy explicit crash test" in res["error"]
