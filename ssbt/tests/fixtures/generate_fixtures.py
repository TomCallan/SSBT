"""Generate synthetic OHLCV fixture data for regression tests.

Produces deterministic parquet files used by conftest.py test fixtures.
Run from repo root: python -m tests.fixtures.generate_fixtures
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def generate_synthetic_ohlcv(
    n_bars: int = 5000,
    start_price: float = 100.0,
    drift: float = 0.0001,
    volatility: float = 0.01,
    seed: int = 42,
) -> pl.DataFrame:
    """Deterministic synthetic OHLCV — mirrors ssbt.examples.sma_cross."""
    rng = np.random.default_rng(seed)

    returns = rng.normal(drift, volatility, n_bars)
    close = start_price * np.cumprod(1 + returns)

    intrabar_range = np.abs(rng.normal(0, volatility, n_bars)) * close
    open_ = np.roll(close, 1)
    open_[0] = start_price
    high = np.maximum(open_, close) + intrabar_range * rng.uniform(0.1, 0.5, n_bars)
    low = np.minimum(open_, close) - intrabar_range * rng.uniform(0.1, 0.5, n_bars)
    volume = rng.lognormal(15, 1, n_bars)

    ts = (np.datetime64("2020-01-01").astype("datetime64[ns]").astype(np.int64)
          + np.arange(n_bars) * 86_400_000_000_000)

    return pl.DataFrame({
        "timestamp": ts,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def generate_multi_symbol_data(
    n_bars: int = 5000,
    seed: int = 42,
) -> dict[str, pl.DataFrame]:
    """Deterministic multi-symbol synthetic data — mirrors examples.multi_symbol."""
    rng = np.random.default_rng(seed)
    ts = (np.datetime64("2023-01-01").astype("datetime64[ns]").astype(np.int64)
          + np.arange(n_bars) * 86_400_000_000_000)

    symbols = {}
    for name, start, vol, drift_val in [
        ("BTC", 30000, 0.02, 0.0005),
        ("ETH", 2000, 0.025, 0.0003),
        ("SOL", 100, 0.035, 0.0008),
    ]:
        r = rng.normal(drift_val, vol, n_bars)
        close = start * np.cumprod(1 + r)
        ib = np.abs(rng.normal(0, 0.01, n_bars)) * close
        symbols[name] = pl.DataFrame({
            "timestamp": ts,
            "open": np.roll(close, 1),
            "high": np.maximum(np.roll(close, 1), close) + ib * 0.3,
            "low": np.minimum(np.roll(close, 1), close) - ib * 0.3,
            "close": close,
            "volume": rng.lognormal(18, 1, n_bars),
        })
    return symbols


def main():
    df = generate_synthetic_ohlcv()
    path = DATA_DIR / "synthetic_ohlcv.parquet"
    df.write_parquet(path)
    print(f"Generated {len(df)} bars -> {path}")

    multi = generate_multi_symbol_data()
    for sym, mdf in multi.items():
        mp = DATA_DIR / f"{sym.lower()}_data.parquet"
        mdf.write_parquet(mp)
        print(f"  Multi {sym}: {len(mdf)} bars -> {mp}")


if __name__ == "__main__":
    main()
