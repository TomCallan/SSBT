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
    sub_bar_splits: int = 1,
    spread_pct: float = 0.0002,
    depth_levels: int = 5,
    base_depth_qty: float = 100.0,
) -> list[OrderBookQuote]:
    """Reconstruct synthetic L2 orderbook quotes at arbitrary target resolution (y) from base resolution data (x).
    
    If sub_bar_splits > 1 (e.g. sub_bar_splits=60 to reconstruct 1-minute orderbook quotes from 1-hour bars,
    or sub_bar_splits=60 to reconstruct 1-second quotes from 1-minute bars), it synthesizes intrabar sub-quotes.
    """
    if bar_df.is_empty():
        return []

    quotes: list[OrderBookQuote] = []
    
    timestamps = bar_df["timestamp"].to_list()
    symbols = bar_df["symbol"].to_list() if "symbol" in bar_df.columns else ["SYNTH"] * len(bar_df)
    opens = bar_df["open"].to_list() if "open" in bar_df.columns else bar_df["close"].to_list()
    highs = bar_df["high"].to_list() if "high" in bar_df.columns else bar_df["close"].to_list()
    lows = bar_df["low"].to_list() if "low" in bar_df.columns else bar_df["close"].to_list()
    closes = bar_df["close"].to_list()
    volumes = bar_df["volume"].to_list() if "volume" in bar_df.columns else [1000.0] * len(bar_df)

    n_bars = len(bar_df)
    
    # Calculate average bar step delta in nanoseconds/milliseconds
    step_delta = 60_000
    if n_bars > 1:
        step_delta = max(int((timestamps[-1] - timestamps[0]) / (n_bars - 1)), 1)

    sub_step = int(step_delta / max(sub_bar_splits, 1))

    for i in range(n_bars):
        ts_start = timestamps[i]
        sym = symbols[i]
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        vol = volumes[i] / max(sub_bar_splits, 1)

        # Synthesize price trajectory across sub_bar_splits
        if sub_bar_splits == 1:
            price_points = [c]
        else:
            # Trajectory: Open -> Low/High -> Close
            mid = sub_bar_splits // 2
            p1 = np.linspace(o, l if c >= o else h, mid, endpoint=False)
            p2 = np.linspace(l if c >= o else h, c, sub_bar_splits - mid)
            price_points = np.concatenate([p1, p2])

        for s_idx, price in enumerate(price_points):
            ts = ts_start + (s_idx * sub_step)
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
        sub_bar_splits: int = 1,
        spread_pct: float = 0.0002,
        depth_levels: int = 5,
    ) -> list[OrderBookQuote]:
        """Reconstruct L2 orderbook quotes at arbitrary target resolution (y) from base resolution data (x)."""
        return rebuild_orderbook_from_bars(
            bar_df,
            sub_bar_splits=sub_bar_splits,
            spread_pct=spread_pct,
            depth_levels=depth_levels,
        )

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
