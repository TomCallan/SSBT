"""Orderbook Engine & Arbitrary-Resolution L2 Orderbook Reconstruction Module for SSBT.

Supports taking data of ANY base resolution (x = 1d, 4h, 1h, 15m, 1m, etc.) and synthesizing
higher-resolution L2 orderbook quotes (y = sub-bar ticks/seconds/minutes) with multi-level bid/ask depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import numpy as np
import polars as pl


@dataclass
class OrderBookQuote:
    """L2 Orderbook Quote event with depth levels."""
    timestamp: int
    symbol: str
    bids: list[tuple[float, float]] = field(default_factory=list)  # (price, qty)
    asks: list[tuple[float, float]] = field(default_factory=list)  # (price, qty)

    @property
    def bid(self) -> float:
        return self.bids[0][0] if self.bids else 0.0

    @property
    def ask(self) -> float:
        return self.asks[0][0] if self.asks else 0.0

    @property
    def bid_qty(self) -> float:
        return self.bids[0][1] if self.bids else 0.0

    @property
    def ask_qty(self) -> float:
        return self.asks[0][1] if self.asks else 0.0


def rebuild_orderbook_from_bars(
    bar_df: pl.DataFrame,
    spread_pct: float = 0.0002,
    depth_levels: int = 5,
    base_depth_qty: float = 100.0,
) -> list[OrderBookQuote]:
    """Convert bar prices into multi-level L2 depth quotes."""
    if bar_df.is_empty():
        return []

    quotes: list[OrderBookQuote] = []
    
    timestamps = bar_df["timestamp"].to_list()
    symbols = bar_df["symbol"].to_list() if "symbol" in bar_df.columns else ["SYNTH"] * len(bar_df)
    closes = bar_df["close"].to_list()
    volumes = bar_df["volume"].to_list() if "volume" in bar_df.columns else [1000.0] * len(bar_df)

    for i in range(len(bar_df)):
        ts = timestamps[i]
        sym = symbols[i]
        price = closes[i]
        vol = volumes[i]

        half_spread = price * (spread_pct / 2.0)
        top_bid = price - half_spread
        top_ask = price + half_spread
        level_vol = max(vol / (depth_levels * 2.0), base_depth_qty)

        bids = []
        asks = []

        for lvl in range(depth_levels):
            level_step = price * 0.0001 * (lvl + 1)
            b_price = round(top_bid - level_step, 4)
            a_price = round(top_ask + level_step, 4)
            l_qty = round(level_vol * (1.0 + 0.1 * lvl), 2)
            
            bids.append((b_price, l_qty))
            asks.append((a_price, l_qty))

        quotes.append(OrderBookQuote(
            timestamp=int(ts),
            symbol=str(sym),
            bids=bids,
            asks=asks,
        ))

    return quotes


class OrderBookEngine:
    """Orderbook Reconstruction & Ingestion Engine."""

    @staticmethod
    def reconstruct(
        bar_df: pl.DataFrame,
        spread_pct: float = 0.0002,
        depth_levels: int = 5,
    ) -> list[OrderBookQuote]:
        """Convert bar prices into multi-level L2 depth quotes."""
        return rebuild_orderbook_from_bars(
            bar_df,
            spread_pct=spread_pct,
            depth_levels=depth_levels,
        )

    @staticmethod
    def apply_multi_resolution_sources(
        base_df: pl.DataFrame,
        resolution_sources: list[pl.DataFrame],
        spread_pct: float = 0.0002,
        depth_levels: int = 5,
    ) -> list[OrderBookQuote]:
        """Apply multi-resolution fallback data feeds to base decision bars.
        
        Evaluates time windows of base_df (e.g. 1-hour bars). For each window, uses the highest-priority
        resolution source available (e.g. 1-min -> 5-min -> 15-min -> 1-hour fallback).
        """
        if base_df.is_empty():
            return []

        all_quotes: list[OrderBookQuote] = []
        base_sorted = base_df.sort("timestamp")
        base_ts = base_sorted["timestamp"].to_list()

        n_base = len(base_ts)
        step_delta = 3600_000
        if n_base > 1:
            step_delta = max(int((base_ts[-1] - base_ts[0]) / (n_base - 1)), 1)

        for i in range(n_base):
            t_start = base_ts[i]
            t_end = t_start + step_delta

            matched_quotes = None

            # Try higher-resolution sources in priority order
            for src_df in resolution_sources:
                if src_df is None or src_df.is_empty():
                    continue
                
                # Filter rows in current time window [t_start, t_end)
                window_df = src_df.filter(
                    (pl.col("timestamp") >= t_start) & (pl.col("timestamp") < t_end)
                )

                if window_df.height > 0:
                    matched_quotes = rebuild_orderbook_from_bars(
                        window_df,
                        spread_pct=spread_pct,
                        depth_levels=depth_levels,
                    )
                    break

            # Fallback: If no higher-resolution source matched, use base bar
            if matched_quotes is None:
                single_bar_df = base_sorted.slice(i, 1)
                matched_quotes = rebuild_orderbook_from_bars(
                    single_bar_df,
                    spread_pct=spread_pct,
                    depth_levels=depth_levels,
                )

            all_quotes.extend(matched_quotes)

        return all_quotes

    @staticmethod
    def to_dataframe(quotes: list[OrderBookQuote]) -> pl.DataFrame:
        """Convert OrderBookQuote objects into a clean Polars DataFrame."""
        if not quotes:
            return pl.DataFrame()

        rows = []
        for q in quotes:
            rows.append({
                "timestamp": q.timestamp,
                "symbol": q.symbol,
                "bid": q.bid,
                "ask": q.ask,
                "bid_qty": q.bid_qty,
                "ask_qty": q.ask_qty,
                "depth_bids_json": json.dumps(q.bids),
                "depth_asks_json": json.dumps(q.asks),
            })
        return pl.DataFrame(rows)


class OrderBookFeed:
    """Event feed streaming OrderBookQuote events."""

    def __init__(self, quotes: list[OrderBookQuote]):
        self.quotes = quotes
        self.cursor = 0

    def has_next(self) -> bool:
        return self.cursor < len(self.quotes)

    def next_quote(self) -> OrderBookQuote | None:
        if not self.has_next():
            return None
        q = self.quotes[self.cursor]
        self.cursor += 1
        return q
