"""Universal Dynamic Data Stream & Forward-Filling Demonstration for SSBT.

Demonstrates combining arbitrary market data sources (Raw Trade Ticks, L2 Orderbook Quotes,
and OHLCV Bars of any resolution) into a single, high-performance tick stream with automatic forward-filling.
"""

import sys
import numpy as np
import polars as pl
from ssbt.data.universal_tick import UniversalTickStream, UniversalTickFeed
from ssbt.core.matching import MatchingEngine
from ssbt.core.events import Side, Order, OrderType, OrderStatus
from ssbt.analytics.terminal import console
from rich.panel import Panel
from rich.table import Table


def main():
    console.print()
    console.print(Panel.fit(
        "[bold cyan]SSBT UNIVERSAL DYNAMIC TICK STREAM & FORWARD-FILLING DEMONSTRATION[/bold cyan]\n"
        "[dim]Dynamic Input: [Raw Ticks] + [L2 Orderbook Depth] + [Forward-Filled OHLCV Bars][/dim]",
        border_style="cyan"
    ))

    # 1. Input Source A: 1-Hour Base Bar Data
    data_1h = pl.DataFrame({
        "timestamp": [1700000000000, 1700003600000],
        "symbol": ["GC=F"] * 2,
        "open": [2000.0, 2005.0],
        "high": [2010.0, 2012.0],
        "low": [1995.0, 2002.0],
        "close": [2005.0, 2008.0],
        "volume": [10000.0, 12000.0],
    })

    # 2. Input Source B: High-Frequency L2 Orderbook Depth Quotes (timestamps within Hour 1)
    data_l2 = pl.DataFrame({
        "timestamp": [1700000100000, 1700000200000],
        "symbol": ["GC=F"] * 2,
        "bid": [2001.0, 2002.0],
        "ask": [2001.5, 2002.5],
        "bid_qty": [150.0, 200.0],
        "ask_qty": [150.0, 200.0],
    })

    # 3. Input Source C: Raw Trade Ticks (timestamps within Hour 1)
    data_ticks = pl.DataFrame({
        "timestamp": [1700000050000, 1700000150000],
        "symbol": ["GC=F"] * 2,
        "price": [2000.5, 2001.8],
        "volume": [10.0, 25.0],
    })

    # Build Unified Dynamic Tick Stream with Forward-Filling
    stream_ticks = UniversalTickStream.build_stream(
        data_sources=[data_1h, data_l2, data_ticks],
        symbol="GC=F",
        spread_pct=0.0002,
        forward_fill=True,
    )

    console.print(f"[bold green][PASS] Successfully Built Unified Dynamic Tick Stream ({len(stream_ticks)} Tick Events)[/bold green]")
    console.print()

    # Display Stream Breakdown Table
    table = Table(title="Unified Chronological Tick Stream (Dynamic Multi-Source Merge)", header_style="bold yellow")
    table.add_column("Timestamp", style="dim")
    table.add_column("Symbol", style="cyan")
    table.add_column("Source Type", style="bold green")
    table.add_column("Price / Mid", style="white")
    table.add_column("Bid / Ask (Forward-Filled)", style="green")

    for t in stream_ticks:
        table.add_row(
            str(t.timestamp),
            t.symbol,
            t.data_source_type,
            f"${t.price:,.2f}",
            f"${t.bid:,.2f} / ${t.ask:,.2f}",
        )

    console.print(table)
    console.print()

    # 4. Test Matching Pending Orders Against Universal Tick Stream
    matching = MatchingEngine()
    limit_buy = Order(id=1, symbol="GC=F", side=Side.BUY, type=OrderType.LIMIT, qty=1.0, price=2001.5, status=OrderStatus.PENDING)
    matching.submit(limit_buy)

    fills = []
    feed = UniversalTickFeed(stream_ticks)
    while feed.has_next():
        tick = feed.next_tick()
        f_list = matching.process_tick(tick)
        fills.extend(f_list)

    console.print(f"[bold green][PASS] Universal Tick Stream Matching Completed! Total Fills Generated: {len(fills)}[/bold green]")
    if fills:
        console.print(f"  - Fill Order ID: {fills[0].order_id} | Price: ${fills[0].price:,.2f} | Qty: {fills[0].qty}")
    console.print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
