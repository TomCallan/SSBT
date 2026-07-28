"""Rich terminal output module for SSBT.

Renders high-visibility terminal tables, sparklines, panels, and performance summaries using `rich`.
"""

from __future__ import annotations

from typing import Any
import numpy as np
import polars as pl
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


def display_experiment_summary(result: dict[str, Any], title: str = "SSBT Experiment Results") -> None:
    """Render a clean, rich terminal panel and table for experiment results."""
    events = result.get("events")
    outcomes = result.get("outcomes")
    stats = result.get("statistics", {})

    console.print()
    console.print(Panel.fit(f"[bold cyan]{title}[/bold cyan]", border_style="cyan"))

    # Summary Panel Info
    n_events = events.height if events is not None else 0
    n_outcomes = outcomes.height if outcomes is not None else 0
    console.print(f"[bold white]Events Detected:[/bold white] [bold yellow]{n_events}[/bold yellow]  |  [bold white]Outcomes Computed:[/bold white] [bold yellow]{n_outcomes}[/bold yellow]")
    console.print()

    # Per-Horizon Statistics Table
    by_horizon = stats.get("by_horizon", {})
    if by_horizon:
        table = Table(title="Forward Return Statistics by Horizon", header_style="bold magenta", border_style="dim")
        table.add_column("Horizon (bars)", justify="right", style="cyan")
        table.add_column("Count", justify="right", style="white")
        table.add_column("Mean Return", justify="right", style="green")
        table.add_column("Median Return", justify="right", style="green")
        table.add_column("Hit Rate", justify="right", style="yellow")
        table.add_column("95% Bootstrap CI", justify="center", style="bold blue")

        ci_data = stats.get("confidence", {}).get("by_horizon", {})

        for h in sorted(by_horizon.keys(), key=int):
            h_stat = by_horizon[h]
            count = h_stat.get("count")
            if count is None and outcomes is not None and not outcomes.is_empty():
                count = outcomes.filter(pl.col("horizon") == int(h)).height
            elif count is None:
                count = n_events

            mean_val = h_stat.get("mean", 0.0)
            if isinstance(mean_val, dict):
                mean_val = mean_val.get("estimate", 0.0)

            med_val = h_stat.get("median", 0.0)
            if isinstance(med_val, dict):
                med_val = med_val.get("estimate", 0.0)

            hit_rate = h_stat.get("hit_rate", 0.0)
            if isinstance(hit_rate, dict):
                hit_rate = hit_rate.get("estimate", 0.0)

            ci_str = "N/A"
            if h in ci_data and "mean" in ci_data[h]:
                ci_item = ci_data[h]["mean"]
                ci_str = f"[{ci_item['ci_lower']*100:+.2f}%, {ci_item['ci_upper']*100:+.2f}%]"

            table.add_row(
                f"{h}b",
                str(count),
                f"{mean_val*100:+.2f}%",
                f"{med_val*100:+.2f}%",
                f"{hit_rate*100:.1f}%",
                ci_str,
            )
        console.print(table)
        console.print()


def display_backtest_summary(metrics: dict[str, Any], trades_df: pl.DataFrame | None = None) -> None:
    """Render a rich terminal table for backtest performance metrics and trades."""
    console.print()
    console.print(Panel.fit("[bold green]SSBT Backtest Performance Report[/bold green]", border_style="green"))

    table = Table(header_style="bold yellow", border_style="dim")
    table.add_column("Metric", style="bold white")
    table.add_column("Value", justify="right", style="bold cyan")

    table.add_row("Sharpe Ratio", f"{metrics.get('sharpe', 0.0):.2f}")
    table.add_row("Sortino Ratio", f"{metrics.get('sortino', 0.0):.2f}")
    table.add_row("Calmar Ratio", f"{metrics.get('calmar', 0.0):.2f}")
    table.add_row("Max Drawdown", f"{metrics.get('max_drawdown', 0.0)*100:.2f}%")
    table.add_row("Win Rate", f"{metrics.get('win_rate', 0.0)*100:.1f}%")
    table.add_row("Profit Factor", f"{metrics.get('profit_factor', 0.0):.2f}")

    console.print(table)

    if trades_df is not None and not trades_df.is_empty():
        trade_table = Table(title=f"Trades Log (Showing top {min(10, trades_df.height)} of {trades_df.height})", header_style="bold blue", border_style="dim")
        trade_table.add_column("Symbol", style="cyan")
        trade_table.add_column("Side", style="white")
        trade_table.add_column("Entry Price", justify="right", style="white")
        trade_table.add_column("Exit Price", justify="right", style="white")
        trade_table.add_column("PnL ($)", justify="right", style="bold green")
        trade_table.add_column("PnL (%)", justify="right", style="bold green")

        for row in trades_df.head(10).iter_rows(named=True):
            pnl_val = row.get("pnl", 0.0)
            pnl_pct = row.get("pnl_pct", 0.0) * 100
            color = "green" if pnl_val >= 0 else "red"

            trade_table.add_row(
                str(row.get("symbol", "")),
                str(row.get("side", "")),
                f"{row.get('entry_price', 0.0):.2f}",
                f"{row.get('exit_price', 0.0):.2f}",
                f"[{color}]{pnl_val:+,.2f}[/{color}]",
                f"[{color}]{pnl_pct:+.2f}%[/{color}]",
            )
        console.print(trade_table)


def display_audit_status(audit_report: Any) -> None:
    """Render a rich status panel for the audit report."""
    console.print()
    if audit_report.is_valid:
        banner = Panel.fit(
            f"[bold green][PASS] AUDIT PASSED[/bold green]\n"
            f"[white]Checks Passed:[/white] [bold yellow]{audit_report.checks_passed}[/bold yellow]\n"
            f"[white]Lineage Records:[/white] [bold yellow]{audit_report.lineage_records}[/bold yellow]\n"
            f"[white]Integrity SHA-256:[/white] [dim]{audit_report.integrity_hash[:16]}...[/dim]",
            border_style="green",
            title="Execution Integrity & Anti-Lookahead Audit",
        )
    else:
        violations_str = "\n".join([f"  - {v}" for v in audit_report.violations])
        banner = Panel.fit(
            f"[bold red][FAIL] AUDIT FAILED[/bold red]\n"
            f"[bold white]Violations Detected:[/bold white]\n{violations_str}",
            border_style="red",
            title="Execution Integrity Audit Violation",
        )
    console.print(banner)
