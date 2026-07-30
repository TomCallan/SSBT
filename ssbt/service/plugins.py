"""SSBT Strategy Plugin Architecture & Dry-Run Engine.

Provides plugin compatibility verification and ultra-fast 5-bar dry-run testing
for strategies prior to full backtest execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import polars as pl
from packaging.version import Version

import ssbt
from ssbt.core.engine import Engine
from ssbt.data.feed import InMemoryFeed
from ssbt.quick import generate_synthetic_bars
from ssbt.service.runner import _instantiate_strategy
from ssbt.service.schemas import StrategySpec


@dataclass
class PluginManifest:
    name: str
    version: str
    min_ssbt_version: str = "0.1.0"
    entrypoint: str = "main"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_plugin_compatibility(manifest: PluginManifest) -> dict[str, Any]:
    """Verify if current SSBT version satisfies plugin's minimum version requirement.

    Returns a status dictionary containing compatibility metrics and details.
    """
    current_ver_str = getattr(ssbt, "__version__", "0.1.0")
    try:
        current_ver = Version(current_ver_str)
        min_ver = Version(manifest.min_ssbt_version)
        is_compatible = current_ver >= min_ver
        error_msg = (
            None
            if is_compatible
            else f"Current SSBT version ({current_ver_str}) is lower than required ({manifest.min_ssbt_version})."
        )
    except Exception as e:
        is_compatible = False
        error_msg = f"Version comparison error: {e}"

    return {
        "compatible": is_compatible,
        "plugin_name": manifest.name,
        "plugin_version": manifest.version,
        "min_ssbt_version": manifest.min_ssbt_version,
        "current_ssbt_version": current_ver_str,
        "error": error_msg,
    }


def dry_run_strategy(
    strategy_spec: StrategySpec,
    data_sample: pl.DataFrame | None = None,
    symbol: str = "DRY_RUN",
) -> dict[str, Any]:
    """Instantiate strategy and run a fast 5-bar execution check.

    Slices 5 bars from data_sample (or generates synthetic 5 bars if None),
    executes engine run, and returns dry-run summary dictionary.
    """
    try:
        # Convert non-polars dataframe if necessary
        df_input = data_sample
        if df_input is not None and not isinstance(df_input, pl.DataFrame):
            if type(df_input).__module__.startswith("pandas"):
                df_input = pl.from_pandas(df_input)
            elif isinstance(df_input, dict):
                df_input = pl.DataFrame(df_input)
            elif hasattr(df_input, "to_polars"):
                df_input = df_input.to_polars()

        # Prepare 5-bar sample data
        if df_input is not None and len(df_input) > 0:
            df_5 = df_input.head(5)
        else:
            df_5 = generate_synthetic_bars(n_bars=5, seed=42)

        if "timestamp" in df_5.columns:
            dtype = df_5["timestamp"].dtype
            if isinstance(dtype, (pl.Datetime, pl.Date)) or dtype in (pl.Datetime, pl.Date):
                df_5 = df_5.with_columns(pl.col("timestamp").dt.epoch("ms"))

        # Instantiate strategy from spec
        strat = _instantiate_strategy(strategy_spec)
        strategy_name = (
            getattr(strat, "name", None)
            or strategy_spec.name
            or type(strat).__name__
        )

        # Setup feed & run engine
        feed = InMemoryFeed(df_5, symbol=symbol)
        engine = Engine(feed=feed, strategy=strat)
        res = engine.run()

        bars_processed = getattr(res, "n_events", len(df_5))
        orders_submitted = engine.matching._next_order_id - 1
        fills_count = len(res.fills)

        return {
            "dry_run_passed": True,
            "strategy_name": strategy_name,
            "bars_processed": bars_processed,
            "orders_submitted": orders_submitted,
            "fills_count": fills_count,
            "error": None,
        }
    except Exception as e:
        return {
            "dry_run_passed": False,
            "strategy_name": strategy_spec.name or "UnknownStrategy",
            "bars_processed": 0,
            "orders_submitted": 0,
            "fills_count": 0,
            "error": str(e),
        }
