"""Data feed — Parquet or in-memory DataFrames, emits events chronologically.

Performance: InMemoryFeed caches NumPy arrays. to_arrays() for engine fast path.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Union

import numpy as np
import polars as pl

from ssbt.core.events import Bar, BidAsk

_BAR_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}
_BA_COLUMNS = {"timestamp", "bid", "ask"}


def _detect_columns(df: pl.DataFrame, symbol: str) -> str:
    cols = {c.lower() for c in df.columns}
    if _BAR_COLUMNS.issubset(cols):
        return "bar"
    if _BA_COLUMNS.issubset(cols):
        return "ba"
    raise ValueError(
        f"Cannot detect data type for {symbol}. "
        f"Need columns: {_BAR_COLUMNS} (bar) or {_BA_COLUMNS} (bid/ask). "
        f"Got: {cols}"
    )


def _normalise_bar_df(df: pl.DataFrame) -> pl.DataFrame:
    rename = {c: c.lower() for c in df.columns if c != c.lower()}
    if rename:
        df = df.rename(rename)
    return df.select([
        pl.col("timestamp"),
        pl.col("open").cast(pl.Float64),
        pl.col("high").cast(pl.Float64),
        pl.col("low").cast(pl.Float64),
        pl.col("close").cast(pl.Float64),
        pl.col("volume").cast(pl.Float64),
    ]).sort("timestamp")


def _normalise_ba_df(df: pl.DataFrame) -> pl.DataFrame:
    rename = {c: c.lower() for c in df.columns if c != c.lower()}
    if rename:
        df = df.rename(rename)
    return df.select([
        pl.col("timestamp"),
        pl.col("bid").cast(pl.Float64),
        pl.col("ask").cast(pl.Float64),
    ]).sort("timestamp")


class InMemoryFeed:
    """Feed from a pre-loaded DataFrame. No Parquet I/O. Fastest for sweeps.

    Accepts a single-symbol DataFrame with bar or bid/ask columns.
    Optionally slice rows [start:end] for walk-forward windows.
    """

    def __init__(self, df: pl.DataFrame, symbol: str, start: int = 0, end: int | None = None):
        self._symbol = symbol
        self._dtype = _detect_columns(df, symbol)

        if self._dtype == "bar":
            df = _normalise_bar_df(df)
        else:
            df = _normalise_ba_df(df)

        if start > 0 or end is not None:
            df = df.slice(start, (end or len(df)) - start)

        self._df = df
        self._n = len(df)
        self._cached_arrays: dict[str, np.ndarray] = {}
        for col in df.columns:
            self._cached_arrays[col] = df[col].to_numpy()

    @property
    def symbols(self) -> list[str]:
        return [self._symbol]

    @property
    def dtype(self) -> str:
        return self._dtype

    @property
    def n_bars(self) -> int:
        return self._n

    def get_dataframe(self, symbol: str | None = None) -> pl.DataFrame:
        return self._df

    def to_arrays(self) -> dict[str, np.ndarray]:
        """Return raw NumPy arrays for engine fast path. No Bar/BidAsk object creation."""
        return self._cached_arrays

    def __iter__(self) -> Iterator[Union[Bar, BidAsk]]:
        ts = self._cached_arrays["timestamp"]
        sym = self._symbol

        if self._dtype == "bar":
            o = self._cached_arrays["open"]
            h = self._cached_arrays["high"]
            l = self._cached_arrays["low"]
            c = self._cached_arrays["close"]
            v = self._cached_arrays["volume"]
            for i in range(self._n):
                yield Bar(
                    timestamp=int(ts[i]),
                    symbol=sym,
                    open=float(o[i]),
                    high=float(h[i]),
                    low=float(l[i]),
                    close=float(c[i]),
                    volume=float(v[i]),
                )
        else:
            b = self._cached_arrays["bid"]
            a = self._cached_arrays["ask"]
            for i in range(self._n):
                yield BidAsk(
                    timestamp=int(ts[i]),
                    symbol=sym,
                    bid=float(b[i]),
                    ask=float(a[i]),
                )


class ParquetFeed:
    """Reads one or more Parquet files and yields Bar or BidAsk events.

    For multi-symbol: pass dict of {symbol: path}.
    For sweeps: prefer InMemoryFeed — load once, reuse across runs.
    """

    def __init__(self, path: str | dict[str, str], symbol: str | None = None):
        if isinstance(path, str):
            if symbol is None:
                raise ValueError("symbol required when path is a string")
            self._sources = {symbol: path}
        elif isinstance(path, dict):
            self._sources = path
        else:
            raise TypeError(f"path must be str or dict, got {type(path)}")

        self._dfs: dict[str, pl.DataFrame] = {}
        self._dtypes: dict[str, str] = {}
        for sym, p in self._sources.items():
            df = pl.read_parquet(p)
            dtype = _detect_columns(df, sym)
            self._dtypes[sym] = dtype
            if dtype == "bar":
                df = _normalise_bar_df(df)
            else:
                df = _normalise_ba_df(df)
            self._dfs[sym] = df

    @property
    def symbols(self) -> list[str]:
        return list(self._sources)

    @property
    def dtypes(self) -> dict[str, str]:
        return self._dtypes

    def get_dataframe(self, symbol: str | None = None) -> pl.DataFrame:
        if symbol is None and len(self._sources) == 1:
            symbol = next(iter(self._sources))
        if symbol is None or symbol not in self._sources:
            raise ValueError(
                f"Unknown symbol {symbol}. Available: {list(self._sources)}"
            )
        return self._dfs[symbol]

    def to_inmemory(self, symbol: str | None = None, start: int = 0, end: int | None = None) -> InMemoryFeed:
        """Convert to InMemoryFeed for fast repeated iteration."""
        if symbol is None and len(self._sources) == 1:
            symbol = next(iter(self._sources))
        if symbol is None or symbol not in self._sources:
            raise ValueError(f"Unknown symbol {symbol}. Available: {list(self._sources)}")
        return InMemoryFeed(self._dfs[symbol], symbol, start, end)

    def __iter__(self) -> Iterator[Union[Bar, BidAsk]]:
        if len(self._sources) == 1:
            feed = InMemoryFeed(next(iter(self._dfs.values())), next(iter(self._sources)))
            yield from feed
            return

        tagged: list[tuple[int, str, str]] = []
        for sym, dtype in self._dtypes.items():
            df = self._dfs[sym]
            ts = df["timestamp"].to_numpy()
            for i in range(len(df)):
                tagged.append((int(ts[i]), sym, dtype))

        tagged.sort(key=lambda x: x[0])

        indices: dict[str, int] = {s: 0 for s in self._sources}
        for ts, sym, dtype in tagged:
            idx = indices[sym]
            df = self._dfs[sym]
            if dtype == "bar":
                yield Bar(
                    timestamp=ts,
                    symbol=sym,
                    open=float(df["open"][idx]),
                    high=float(df["high"][idx]),
                    low=float(df["low"][idx]),
                    close=float(df["close"][idx]),
                    volume=float(df["volume"][idx]),
                )
            else:
                yield BidAsk(
                    timestamp=ts,
                    symbol=sym,
                    bid=float(df["bid"][idx]),
                    ask=float(df["ask"][idx]),
                )
            indices[sym] += 1

