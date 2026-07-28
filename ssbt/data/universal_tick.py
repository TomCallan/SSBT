"""Universal Tick Stream & Dynamic Data Merging Engine for SSBT.

Unifies any combination of market data sources (Raw Ticks, L2/L3 Orderbooks, and OHLCV bars of any resolution)
into a single, high-performance stream of GenericTickEvent objects with forward-filling.
"""

from __future__ import annotations

import json
import numpy as np
import polars as pl
from ssbt.core.events import GenericTickEvent


class UniversalTickStream:
    """Universal Tick Stream Engine for dynamic multi-source merging & forward-filling."""

    @staticmethod
    def build_stream(
        data_sources: list[pl.DataFrame],
        symbol: str = "SYNTH",
        spread_pct: float = 0.0002,
        forward_fill: bool = True,
    ) -> list[GenericTickEvent]:
        """Convert and merge any combination of data sources (Ticks, L2/L3 Orderbooks, Bars) into a unified tick stream."""
        if not data_sources:
            return []

        all_ticks: list[GenericTickEvent] = []

        for df in data_sources:
            if df is None or df.is_empty():
                continue

            cols = set(df.columns)
            sym_val = df["symbol"][0] if "symbol" in cols else symbol

            # 1. Source Type A: OHLCV Bar Data (Convert & interpolate into sub-ticks)
            if "close" in cols and "bid" not in cols:
                ts_list = df["timestamp"].to_list()
                closes = df["close"].to_list()
                opens = df["open"].to_list() if "open" in cols else closes
                vols = df["volume"].to_list() if "volume" in cols else [100.0] * len(df)

                for ts, o, c, v in zip(ts_list, opens, closes, vols):
                    half_spread = c * (spread_pct / 2.0)
                    all_ticks.append(GenericTickEvent(
                        timestamp=int(ts),
                        symbol=str(sym_val),
                        price=float(c),
                        bid=float(c - half_spread),
                        ask=float(c + half_spread),
                        bid_qty=float(v / 2.0),
                        ask_qty=float(v / 2.0),
                        volume=float(v),
                        data_source_type="BAR",
                    ))

            # 2. Source Type B: L2 / L3 Orderbook Depth Quotes
            elif {"bid", "ask"}.issubset(cols):
                ts_list = df["timestamp"].to_list()
                bids = df["bid"].to_list()
                asks = df["ask"].to_list()
                bid_qtys = df["bid_qty"].to_list() if "bid_qty" in cols else [100.0] * len(df)
                ask_qtys = df["ask_qty"].to_list() if "ask_qty" in cols else [100.0] * len(df)

                for ts, b, a, b_q, a_q in zip(ts_list, bids, asks, bid_qtys, ask_qtys):
                    mid_p = (b + a) / 2.0
                    all_ticks.append(GenericTickEvent(
                        timestamp=int(ts),
                        symbol=str(sym_val),
                        price=float(mid_p),
                        bid=float(b),
                        ask=float(a),
                        bid_qty=float(b_q),
                        ask_qty=float(a_q),
                        volume=float(b_q + a_q),
                        data_source_type="L2_ORDERBOOK",
                    ))

            # 3. Source Type C: Raw Trade Ticks
            elif "price" in cols:
                ts_list = df["timestamp"].to_list()
                prices = df["price"].to_list()
                vols = df["volume"].to_list() if "volume" in cols else [1.0] * len(df)

                for ts, p, v in zip(ts_list, prices, vols):
                    half_spread = p * (spread_pct / 2.0)
                    all_ticks.append(GenericTickEvent(
                        timestamp=int(ts),
                        symbol=str(sym_val),
                        price=float(p),
                        bid=float(p - half_spread),
                        ask=float(p + half_spread),
                        bid_qty=100.0,
                        ask_qty=100.0,
                        volume=float(v),
                        data_source_type="TICK",
                    ))

        # Sort combined ticks by timestamp
        all_ticks.sort(key=lambda t: t.timestamp)

        # Forward-fill quotes if forward_fill is True
        if forward_fill and len(all_ticks) > 1:
            last_bid = all_ticks[0].bid
            last_ask = all_ticks[0].ask
            last_price = all_ticks[0].price

            for t in all_ticks:
                if t.bid == 0.0 and last_bid > 0.0:
                    t.bid = last_bid
                else:
                    last_bid = t.bid

                if t.ask == 0.0 and last_ask > 0.0:
                    t.ask = last_ask
                else:
                    last_ask = t.ask

                if t.price == 0.0 and last_price > 0.0:
                    t.price = last_price
                else:
                    last_price = t.price

        return all_ticks


class UniversalTickFeed:
    """Feed streaming GenericTickEvent events to strategy and matching engines."""

    def __init__(self, ticks: list[GenericTickEvent]):
        self.ticks = ticks
        self.cursor = 0

    def has_next(self) -> bool:
        return self.cursor < len(self.ticks)

    def next_tick(self) -> GenericTickEvent | None:
        if not self.has_next():
            return None
        t = self.ticks[self.cursor]
        self.cursor += 1
        return t
