"""Arbitrary Resolution Orderbook Reconstruction Example for SSBT.

Demonstrates taking low-resolution base data (x = 1-hour bars) and reconstructing
high-resolution synthetic L2 orderbook quotes (y = 1-minute sub-bar ticks) using OrderBookEngine.

SSBT Data Ingestion Philosophy:
SSBT harnesses ZERO internal data downloading interfaces. All market data (CSV, Parquet, CCXT, SQL)
is ingested externally and fed as Polars DataFrames into SSBT feeds.
"""

import sys
import numpy as np
import polars as pl
from ssbt.data.orderbook import OrderBookEngine, OrderBookFeed
from ssbt.execution.models import RealisticExecutionEngine
from ssbt.core.events import Side
from ssbt.analytics.terminal import console
from rich.panel import Panel
from rich.table import Table


def main():
    console.print()
    console.print(Panel.fit(
        "[bold cyan]SSBT ARBITRARY RESOLUTION ORDERBOOK RECONSTRUCTION DEMONSTRATION[/bold cyan]\n"
        "[dim]Base Resolution x (1-Hour Bars) -> Target Sub-Bar Resolution y (1-Minute L2 Orderbook Ticks)[/dim]",
        border_style="cyan"
    ))

    # 1. Base Data x: 10 Hourly Bars (User External Data)
    n_hourly_bars = 10
    timestamps_1h = np.arange(n_hourly_bars, dtype=np.int64) * 3600_000 + 1_700_000_000_000
    prices_1h = 2000.0 + np.cumsum(np.random.normal(0, 5.0, n_hourly_bars))

    data_1h = pl.DataFrame({
        "timestamp": timestamps_1h,
        "symbol": ["GC=F"] * n_hourly_bars,
        "open": prices_1h,
        "high": prices_1h + 4.0,
        "low": prices_1h - 4.0,
        "close": prices_1h + 1.0,
        "volume": np.full(n_hourly_bars, 10000.0),
    })

    console.print(f"Loaded Base Data x: [bold white]{len(data_1h)} Hourly Bars[/bold white]")

    # 2. Reconstruct High-Resolution Orderbook y (1-Minute Ticks, sub_bar_splits=60)
    quotes_1m = OrderBookEngine.reconstruct(
        data_1h,
        sub_bar_splits=60,  # 60 sub-bar minute ticks per 1-hour bar
        spread_pct=0.0002,
        depth_levels=5,
    )

    orderbook_df = OrderBookEngine.to_dataframe(quotes_1m)
    console.print(f"[bold green][PASS] Reconstructed {len(quotes_1m)} 1-Minute L2 Orderbook Quotes (y) from {len(data_1h)} Hourly Bars (x)![/bold green]")
    console.print()

    # Display Reconstructed Sub-Bar Orderbook Ticks
    table = Table(title="Synthesized 1-Minute Orderbook Quotes (First 5 Sub-Bar Ticks from Hour 1)", header_style="bold yellow")
    table.add_column("Sub-Tick TS", style="dim")
    table.add_column("Symbol", style="cyan")
    table.add_column("Top Bid (Price @ Qty)", style="green")
    table.add_column("Top Ask (Price @ Qty)", style="red")
    table.add_column("Level 5 Bid", style="dim green")
    table.add_column("Level 5 Ask", style="dim red")

    for q in quotes_1m[:5]:
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

    # 3. Test Execution Against Orderbook Depth
    exec_engine = RealisticExecutionEngine(base_slippage_bps=1.0, commission_bps=1.0)
    fill_res = exec_engine.process_execution(price=quotes_1m[0].ask, qty=150.0, side=Side.BUY, bar_volume=quotes_1m[0].ask_qty * 10)

    console.print("[bold yellow]Execution Against Sub-Bar Orderbook Depth Result:[/bold yellow]")
    console.print(f"  - Requested Qty: 150.0")
    console.print(f"  - Executed Qty: {fill_res['executed_qty']:.1f}")
    console.print(f"  - Executed Price: ${fill_res['executed_price']:,.2f}")
    console.print(f"  - Is Partially Filled: [bold cyan]{fill_res['is_partially_filled']}[/bold cyan]")
    console.print()

    console.print("[bold green]Arbitrary Resolution Orderbook Engine Completed Successfully![/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
