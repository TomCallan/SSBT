"""Orderbook Engine & Synthetic L2 Orderbook Reconstruction Module for SSBT.

Provides OrderBookQuote, OrderBookFeed, and utilities to reconstruct high-resolution
synthetic L2 orderbook depth quotes from lower-resolution bar data (minute/hourly bars).
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    """Reconstruct high-resolution synthetic L2 orderbook depth quotes from minute/hourly bar data.
    
    Generates realistic multi-level bid/ask depth quotes for every bar, allowing
    orderbook execution engines to match orders against depth liquidity.
    """
    if bar_df.is_empty():
        return []

    quotes: list[OrderBookQuote] = []
    
    timestamps = bar_df["timestamp"].to_list()
    symbols = bar_df["symbol"].to_list() if "symbol" in bar_df.columns else ["SYNTH"] * len(bar_df)
    closes = bar_df["close"].to_list()
    volumes = bar_df["volume"].to_list() if "volume" in bar_df.columns else [1000.0] * len(bar_df)

    for ts, sym, price, vol in zip(timestamps, symbols, closes, volumes):
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
