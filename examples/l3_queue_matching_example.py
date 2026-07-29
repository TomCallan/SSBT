"""Canonical Example: High-Frequency L3 Orderbook Queue Priority & Latency Matching."""

import json
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ssbt import (
    Order, Side, OrderType, OrderStatus,
    QueuePriorityModel, ExecutionLatencyModel, L3MatchingEngine,
    plot_l3_orderbook_dashboard, sync_latest_run_folder, capture_environment_snapshot,
)

console = Console()


def main():
    run_id = f"run_l3_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = Path("artifacts") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(
        f"[bold green]SSBT HIGH-FREQUENCY L3 QUEUE PRIORITY ENGINE[/bold green]\n"
        f"Run ID: [bold cyan]{run_id}[/bold cyan] | Output: [bold cyan]{run_dir}[/bold cyan]",
        border_style="green"
    ))

    # 1. Instantiate L3 Engine with Latency & Queue Priority Models
    latency_model = ExecutionLatencyModel(latency_ms=5.0)
    queue_model = QueuePriorityModel(initial_volume_ahead_pct=0.60)
    l3_engine = L3MatchingEngine(queue_model=queue_model, latency_model=latency_model)

    # 2. Submit Limit Buy Order into Orderbook (Price: $100.0, Level Vol: 50.0)
    buy_order = Order(
        id=201, symbol="BTC", side=Side.BUY, type=OrderType.LIMIT,
        price=100.0, qty=5.0, status=OrderStatus.PENDING
    )
    
    l3_engine.submit_order(buy_order, level_volume=50.0, timestamp=1000)
    console.print(f"[cyan]Submitted Limit BUY Order #201 @ $100.0 (5.0 Qty) into L3 Queue.[/cyan]")
    console.print(f"Initial Volume Ahead in Queue (V_ahead): [bold yellow]30.0 units[/bold yellow]\n")

    # 3. Simulate sequential market trade prints at $100.0 price level
    market_trades = [
        (1010, 100.0, 10.0),
        (1020, 100.0, 12.0),
        (1030, 100.0, 15.0),  # Clears remaining 8.0 v_ahead + fills 5.0 order qty
        (1040, 100.0, 10.0),
    ]

    queue_history = []
    all_fills = []

    tbl = Table(title="L3 Market Trade Stream & Order Queue Depletion", header_style="bold green", border_style="dim")
    tbl.add_column("Timestamp (ms)", justify="center", style="cyan")
    tbl.add_column("Trade Price ($)", justify="right", style="white")
    tbl.add_column("Trade Vol", justify="right", style="yellow")
    tbl.add_column("Queue Vol Ahead (V_ahead)", justify="right", style="bold red")
    tbl.add_column("Order Status", justify="center", style="bold green")

    for ts, price, vol in market_trades:
        fills = l3_engine.process_market_event(price, vol)
        all_fills.extend(fills)

        tracker = queue_model.active_queues.get(201)
        rem_v_ahead = tracker.volume_ahead if tracker else 0.0

        queue_history.append({
            "timestamp": ts,
            "trade_price": price,
            "trade_volume": vol,
            "volume_ahead": rem_v_ahead,
        })

        tbl.add_row(
            str(ts),
            f"${price:.2f}",
            f"{vol:.1f}",
            f"{rem_v_ahead:.1f}",
            str(buy_order.status.value),
        )

    console.print(tbl)
    console.print()

    # 4. Save Plot Artifact (l3_orderbook_dashboard.png)
    chart_path = run_dir / "l3_orderbook_dashboard.png"
    plot_l3_orderbook_dashboard(
        queue_history=queue_history,
        title="HFT L3 Orderbook Queue Depletion & Price-Time Execution Audit",
        save_path=str(chart_path),
    )
    console.print(f"[bold green][PASS] Saved L3 Orderbook Dashboard Plot to:[/bold green] [bold cyan]{chart_path.resolve()}[/bold cyan]")

    # 5. Save JSON & Environment Artifacts
    l3_audit = {
        "order_id": buy_order.id,
        "submission_latency_ms": latency_model.latency_ms,
        "initial_v_ahead": 30.0,
        "final_status": buy_order.status.value,
        "total_fills": len(all_fills),
    }
    with open(run_dir / "l3_execution_audit.json", "w") as f:
        json.dump(l3_audit, f, indent=2)

    capture_environment_snapshot(run_dir)

    # 6. Sync 1-to-1 to artifacts/latest/
    sync_latest_run_folder(run_dir)
    console.print(f"[bold green][PASS] Synced Run Assets to Artifacts Latest Folder:[/bold green] [bold cyan]{(Path('artifacts') / 'latest').resolve()}[/bold cyan]")


if __name__ == "__main__":
    main()
