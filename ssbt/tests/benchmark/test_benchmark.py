"""Performance benchmarks for event detection and outcome calculation."""

import time
import numpy as np
import polars as pl
import pytest

from ssbt.events.volume_spike import VolumeSpike
from ssbt.outcomes.forward_return import ForwardReturn


def test_event_detection_performance():
    n_bars = 50_000
    timestamps = np.arange(n_bars, dtype=np.int64) * 60_000_000_000
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n_bars) * 0.5)
    volumes = np.random.exponential(1000.0, size=n_bars)
    
    df = pl.DataFrame({
        "timestamp": timestamps,
        "symbol": ["SYNTH"] * n_bars,
        "open": closes,
        "high": closes + 0.5,
        "low": closes - 0.5,
        "close": closes,
        "volume": volumes,
    })

    event_plugin = VolumeSpike()
    t0 = time.perf_counter()
    events = event_plugin.compute_events(df, {"window": 20, "multiplier": 2.5})
    t1 = time.perf_counter()

    elapsed = t1 - t0
    assert elapsed < 1.0  # Must compute 50k bars in under 1 second
    assert "event_id" in events.columns


def test_outcome_computation_performance():
    n_bars = 50_000
    timestamps = np.arange(n_bars, dtype=np.int64) * 60_000_000_000
    np.random.seed(42)
    closes = 100.0 + np.cumsum(np.random.randn(n_bars) * 0.5)
    volumes = np.random.exponential(1000.0, size=n_bars)
    
    df = pl.DataFrame({
        "timestamp": timestamps,
        "symbol": ["SYNTH"] * n_bars,
        "open": closes,
        "high": closes + 0.5,
        "low": closes - 0.5,
        "close": closes,
        "volume": volumes,
    })

    event_plugin = VolumeSpike()
    events = event_plugin.compute_events(df, {"window": 20, "multiplier": 2.5})

    outcome_plugin = ForwardReturn()
    t0 = time.perf_counter()
    outcomes = outcome_plugin.compute_outcomes(df, events, {"horizons": [1, 5, 10, 20]})
    t1 = time.perf_counter()

    elapsed = t1 - t0
    assert elapsed < 1.0  # Must compute outcomes for 50k bars in under 1 second
    assert "value" in outcomes.columns
