"""Orderbook Depth Reconstruction & Microstructure Execution Demonstration for SSBT.

Demonstrates converting external OHLCV bar data into 5-level L2 orderbook quotes
and matching orders against orderbook depth using RealisticExecutionEngine.

SSBT Data Ingestion Philosophy:
SSBT harnesses ZERO internal data downloading interfaces. All market data (CSV, Parquet, CCXT, SQL)
is ingested externally and fed as Polars DataFrames into SSBT feeds.
"""

import sys
import numpy as np
import polars as pl
from ssbt.data.orderbook import OrderBookEngine
from ssbt.execution.models import RealisticExecutionEngine
from ssbt.core.events import Side
from ssbt.analytics.terminal import console
from rich.panel import Panel
from rich.table import Table


def main():
    console.print()
    console.print(Panel.fit(
        "[bold cyan]SSBT ORDERBOOK DEPTH & MICROSTRUCTURE DEMONSTRATION[/bold cyan]\n"
        "[dim]Converting Market Bars into 5-Level L2 Depth Quotes & Order Matching[/dim]",
        border_style="cyan"
    ))

    # 1. Base Data: 10 Bars (User External Data)
    n_bars = 10
    timestamps = np.arange(n_bars, dtype=np.int64) * 60_000 + 1_700_000_000_000
    prices = 2000.0 + np.cumsum(np.random.normal(0, 2.0, n_bars))

    data_bars = pl.DataFrame({
        "timestamp": timestamps,
        "symbol": ["GC=F"] * n_bars,
        "open": prices,
        "high": prices + 2.0,
        "low": prices - 2.0,
        "close": prices + 0.5,
        "volume": np.full(n_bars, 5000.0),
    })

    console.print(f"Loaded Base Data: [bold white]{len(data_bars)} Bars[/bold white]")

    # 2. Reconstruct L2 Depth Quotes
    quotes = OrderBookEngine.reconstruct(
        data_bars,
        spread_pct=0.0002,
        depth_levels=5,
    )

    orderbook_df = OrderBookEngine.to_dataframe(quotes)
    console.print(f"[bold green][PASS] Reconstructed {len(quotes)} L2 Orderbook Depth Quotes![/bold green]")
    console.print()

    # Display Reconstructed Orderbook Ticks
    table = Table(title="Synthesized 5-Level Orderbook Depth Quotes (First 5 Bars)", header_style="bold yellow")
    table.add_column("Timestamp", style="dim")
    table.add_column("Symbol", style="cyan")
    table.add_column("Top Bid (Price @ Qty)", style="green")
    table.add_column("Top Ask (Price @ Qty)", style="red")
    table.add_column("Level 5 Bid", style="dim green")
    table.add_column("Level 5 Ask", style="dim red")

    for q in quotes[:5]:
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
    fill_res = exec_engine.process_execution(price=quotes[0].ask, qty=150.0, side=Side.BUY, bar_volume=quotes[0].ask_qty * 10)

    console.print("[bold yellow]Execution Against Orderbook Depth Result:[/bold yellow]")
    console.print(f"  - Requested Qty: 150.0")
    console.print(f"  - Executed Qty: {fill_res['executed_qty']:.1f}")
    console.print(f"  - Executed Price: ${fill_res['executed_price']:,.2f}")
    console.print(f"  - Is Partially Filled: [bold cyan]{fill_res['is_partially_filled']}[/bold cyan]")
    console.print()

    console.print("[bold green]Orderbook Engine Completed Successfully![/bold green]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
