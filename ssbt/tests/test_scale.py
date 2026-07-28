"""Scale tests for large datasets."""

import time
import numpy as np
import polars as pl
import pytest

from ssbt.events.volume_spike import VolumeSpike
from ssbt.outcomes.forward_return import ForwardReturn


def test_scale_large_dataset_100k():
    n_bars = 100_000
    timestamps = np.arange(n_bars, dtype=np.int64) * 60_000_000_000
    np.random.seed(123)
    closes = 100.0 + np.cumsum(np.random.randn(n_bars) * 0.1)
    volumes = np.random.exponential(5000.0, size=n_bars)

    df = pl.DataFrame({
        "timestamp": timestamps,
        "symbol": ["SYNTH"] * n_bars,
        "open": closes,
        "high": closes + 0.2,
        "low": closes - 0.2,
        "close": closes,
        "volume": volumes,
    })

    t0 = time.perf_counter()
    events = VolumeSpike().compute_events(df, {"window": 50, "multiplier": 3.0})
    outcomes = ForwardReturn().compute_outcomes(df, events, {"horizons": [1, 5, 20, 50]})
    t1 = time.perf_counter()

    duration = t1 - t0
    # Scalability target: 100k bars event & outcome processing within 2 seconds
    assert duration < 2.0
    assert events.height > 0
    assert outcomes.height > 0
