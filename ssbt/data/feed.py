"""Parquet data feed — reads OHLCV or bid/ask data, emits events chronologically."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Union

import polars as pl

from ssbt.core.events import Bar, BidAsk

# Column name mappings: lowercase normalised
_BAR_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}
_BA_COLUMNS = {"timestamp", "bid", "ask"}


def _detect_columns(df: pl.DataFrame, symbol: str) -> str:
    """Detect whether DataFrame is bar or bid/ask based on columns present."""
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


class ParquetFeed:
    """Reads one or more Parquet files and yields Bar or BidAsk events in chronological order.

    Supports multi-symbol: pass dict of {symbol: path}.
    All symbols are merged by timestamp and yielded in global time order.
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

    def __iter__(self) -> Iterator[Union[Bar, BidAsk]]:
        # Load each source, detect type, collect as tagged rows
        frames: list[tuple[str, str, pl.DataFrame]] = []
        _types: dict[str, str] = {}

        for sym, p in self._sources.items():
            df = pl.read_parquet(p)
            dtype = _detect_columns(df, sym)
            _types[sym] = dtype

            if dtype == "bar":
                df = df.select([
                    pl.col("timestamp"),
                    pl.col("open").cast(pl.Float64),
                    pl.col("high").cast(pl.Float64),
                    pl.col("low").cast(pl.Float64),
                    pl.col("close").cast(pl.Float64),
                    pl.col("volume").cast(pl.Float64),
                ]).sort("timestamp")
            else:
                needed = {"timestamp", "bid", "ask"}
                cols = {c.lower() for c in df.columns}
                rename = {c: c.lower() for c in df.columns if c != c.lower()}
                if rename:
                    df = df.rename(rename)
                missing = needed - {c.lower() for c in df.columns}
                if missing:
                    raise ValueError(f"Missing columns {missing} for {sym}")
                df = df.select([
                    pl.col("timestamp"),
                    pl.col("bid").cast(pl.Float64),
                    pl.col("ask").cast(pl.Float64),
                ]).sort("timestamp")

            frames.append((sym, dtype, df))

        # Merge all frames by timestamp
        tagged: list[tuple[int, str, str, pl.DataFrame]] = []
        for sym, dtype, df in frames:
            ts = df["timestamp"].to_numpy()
            for i in range(len(df)):
                tagged.append((int(ts[i]), sym, dtype, df.slice(i, 1)))

        tagged.sort(key=lambda x: x[0])

        for ts, sym, dtype, row in tagged:
            if dtype == "bar":
                yield Bar(
                    timestamp=ts,
                    symbol=sym,
                    open=row["open"][0],
                    high=row["high"][0],
                    low=row["low"][0],
                    close=row["close"][0],
                    volume=row["volume"][0],
                )
            else:
                yield BidAsk(
                    timestamp=ts,
                    symbol=sym,
                    bid=row["bid"][0],
                    ask=row["ask"][0],
                )

    def get_dataframe(self, symbol: str | None = None) -> pl.DataFrame:
        """Return the full DataFrame for a symbol (for precompute)."""
        if symbol is None and len(self._sources) == 1:
            symbol = next(iter(self._sources))
        if symbol is None or symbol not in self._sources:
            raise ValueError(
                f"Unknown symbol {symbol}. Available: {list(self._sources)}"
            )
        return pl.read_parquet(self._sources[symbol])

    @property
    def symbols(self) -> list[str]:
        return list(self._sources)


def make_feed(path: str | dict[str, str], symbol: str | None = None) -> ParquetFeed:
    """Convenience factory."""
    return ParquetFeed(path, symbol)
