"""Example demonstrating synthetic L2 Orderbook reconstruction from minute bars and partial fills execution.

SSBT Data Ingestion Philosophy:
SSBT harnesses ZERO internal data downloading interfaces. All market data (CSV, Parquet, CCXT, SQL)
is ingested externally and fed as Polars DataFrames into SSBT feeds.
"""

import sys
import numpy as np
import polars as pl
from ssbt.data.orderbook import rebuild_orderbook_from_bars, OrderBookFeed
from ssbt.strategy.base import Strategy
from ssbt.core.engine import Engine
from ssbt.data.feed import InMemoryFeed
from ssbt.core.events import Side, Order, OrderStatus, OrderType, Bar
from ssbt.execution.models import RealisticExecutionEngine
from ssbt.analytics.terminal import console
from rich.panel import Panel
from rich.table import Table


def main():
    console.print()
    console.print(Panel.fit(
        "[bold cyan]SSBT SYNTHETIC L2 ORDERBOOK RECONSTRUCTION & PARTIAL FILLS DEMONSTRATION[/bold cyan]\n"
        "[dim]Architecture: 100% External Data Ingestion -> Polars Arrow -> L2 Depth Reconstruction[/dim]",
        border_style="cyan"
    ))

    # 1. Simulate 1-minute bar data (External Data Source)
    n_bars = 50
    timestamps = np.arange(n_bars, dtype=np.int64) * 60_000 + 1_700_000_000_000
    prices = 2000.0 + np.cumsum(np.random.normal(0, 1.5, n_bars))

    bar_df = pl.DataFrame({
        "timestamp": timestamps,
        "symbol": ["GC=F"] * n_bars,
        "open": prices,
        "high": prices + 1.0,
        "low": prices - 1.0,
        "close": prices + 0.2,
        "volume": np.full(n_bars, 500.0),
    })

    # 2. Rebuild Synthetic L2 Orderbook Quotes (5 Depth Levels)
    quotes = rebuild_orderbook_from_bars(bar_df, spread_pct=0.0002, depth_levels=5)
    console.print(f"[bold green][PASS] Reconstructed {len(quotes)} L2 Orderbook Quotes from 1-minute bar data.[/bold green]")

    # Display Top 3 Reconstructed Orderbook Quotes
    table = Table(title="Reconstructed Synthetic L2 Orderbook Depth (First 3 Quotes)", header_style="bold yellow")
    table.add_column("Timestamp", style="dim")
    table.add_column("Symbol", style="cyan")
    table.add_column("Top Bid (Price @ Qty)", style="green")
    table.add_column("Top Ask (Price @ Qty)", style="red")
    table.add_column("Level 5 Bid", style="dim green")
    table.add_column("Level 5 Ask", style="dim red")

    for q in quotes[:3]:
        table.add_row(
            str(q.timestamp),
            q.symbol,
            f"${q.bid:,.2f} ({q.bid_qty:.0f})",
            f"${q.ask:,.2f} ({q.ask_qty:.0f})",
            f"${q.bids[-1][0]:,.2f} ({q.bids[-1][1]:.0f})",
            f"${q.asks[-1][0]:,.2f} ({q.asks[-1][1]:.0f})",
        )

    console.print(table)
    console.print()

    # 3. Demonstrate Partial Fill Execution Engine
    exec_engine = RealisticExecutionEngine(base_slippage_bps=1.0, commission_bps=1.0)
    fill_res = exec_engine.process_execution(price=2000.0, qty=120.0, side=Side.BUY, bar_volume=500.0)

    console.print("[bold yellow]Partial Fill Execution Result (Requested Qty: 120.0, Bar Vol: 500.0, Cap: 10% ADV = 50.0):[/bold yellow]")
    console.print(f"  - Executed Qty: {fill_res['executed_qty']:.1f}")
    console.print(f"  - Executed Price: ${fill_res['executed_price']:,.2f}")
    console.print(f"  - Is Partially Filled: [bold cyan]{fill_res['is_partially_filled']}[/bold cyan]")
    console.print()

    console.print("[bold green]SSBT Orderbook Engine & Partial Fills Demonstration Completed Successfully![/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
