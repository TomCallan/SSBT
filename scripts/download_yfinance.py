"""External YFinance Data Downloader Script (Outside SSBT core package).

Downloads market data externally and supplies Polars DataFrames into SSBT's InMemoryFeed.
"""

from __future__ import annotations
import yfinance as yf
import pandas as pd
import polars as pl
from ssbt.data.feed import InMemoryFeed


def download_yfinance_polars(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
    _raw_df: pd.DataFrame | None = None,
) -> pl.DataFrame:
    """Download market data externally via yfinance and return SSBT-compliant Polars DataFrame."""
    if _raw_df is not None:
        df_pd = _raw_df.copy()
    else:
        ticker = yf.Ticker(symbol)
        df_pd = ticker.history(period=period, interval=interval)
        if df_pd.empty:
            raise ValueError(f"Failed to fetch data for symbol '{symbol}'.")

    if isinstance(df_pd.columns, pd.MultiIndex):
        df_pd.columns = df_pd.columns.get_level_values(0)

    df_pd = df_pd.reset_index()
    date_col = "Date" if "Date" in df_pd.columns else ("Datetime" if "Datetime" in df_pd.columns else df_pd.columns[0])

    rename_dict = {
        date_col: "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    df_pd = df_pd.rename(columns=rename_dict)
    df_pd["symbol"] = symbol

    ts_series = pd.to_datetime(df_pd["timestamp"])
    ts_list = (ts_series.astype("int64") // 10**9).tolist()

    pl_df = pl.DataFrame({
        "timestamp": ts_list,
        "open": df_pd["open"].to_numpy(dtype=float),
        "high": df_pd["high"].to_numpy(dtype=float),
        "low": df_pd["low"].to_numpy(dtype=float),
        "close": df_pd["close"].to_numpy(dtype=float),
        "volume": df_pd["volume"].to_numpy(dtype=float),
        "symbol": [str(s) for s in df_pd["symbol"]],
    })

    return pl_df


def build_ssbt_feed_from_yfinance(
    symbols: list[str] | str,
    period: str = "1y",
    interval: str = "1d",
) -> InMemoryFeed:
    """External helper to download data and supply into SSBT InMemoryFeed."""
    if isinstance(symbols, str):
        symbols = [symbols]

    dfs = [download_yfinance_polars(sym, period=period, interval=interval) for sym in symbols]
    merged_df = pl.concat(dfs) if len(dfs) > 1 else dfs[0]
    return InMemoryFeed(merged_df, symbol=symbols[0])
