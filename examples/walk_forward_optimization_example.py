"""Canonical Example: Rolling Walk-Forward Parameter Optimization with Out-of-Sample Efficiency Audit."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import polars as pl
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ssbt import (
    Strategy, Side, Bar, InMemoryFeed,
    ParameterSpace, IntParam, FloatParam,
    WalkForwardOptimizer, plot_walk_forward_dashboard,
    sync_latest_run_folder, capture_environment_snapshot,
)

console = Console()


class MovingAverageCross(Strategy):
    def __init__(self, fast: int = 10, slow: int = 30):
        super().__init__()
        self.fast = fast
        self.slow = slow
        self.closes = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        if len(self.closes) < self.slow:
            return

        fast_ma = np.mean(self.closes[-self.fast:])
        slow_ma = np.mean(self.closes[-self.slow:])

        if fast_ma > slow_ma and self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty=1.0))
        elif fast_ma < slow_ma and not self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, qty=1.0))


from datetime import datetime

def main():
    run_id = f"run_wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = Path("artifacts") / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(
        f"[bold green]SSBT ROLLING WALK-FORWARD OPTIMIZATION ENGINE[/bold green]\n"
        f"Run ID: [bold cyan]{run_id}[/bold cyan] | Output: [bold cyan]{run_dir}[/bold cyan]",
        border_style="green"
    ))

    # 1. Synthesize market data series
    np.random.seed(42)
    n = 600
    prices = 100.0 + np.cumsum(np.random.randn(n) * 0.8)
    df = pl.DataFrame({
        "timestamp": list(range(1000, 1000 + n * 60, 60)),
        "symbol": ["GC=F"] * n,
        "open": prices,
        "high": prices + 0.6,
        "low": prices - 0.6,
        "close": prices,
        "volume": [1000.0] * n,
    })

    feed = InMemoryFeed(df, symbol="GC=F")

    # 2. Define Parameter Search Space
    space = ParameterSpace()
    space.add(IntParam("fast", start=5, stop=15, step=5))
    space.add(IntParam("slow", start=20, stop=40, step=10))

    # 3. Instantiate and execute WalkForwardOptimizer
    wf_opt = WalkForwardOptimizer(
        strategy_cls=MovingAverageCross,
        param_space=space,
        is_bars=150,
        oos_bars=50,
        initial_cash=5000.0,
    )

    console.print("[cyan]Running Rolling In-Sample / Out-of-Sample Walk-Forward Optimization...[/cyan]")
    wf_res = wf_opt.run(feed)

    # 4. Display Window Metrics Table
    tbl = Table(title="Rolling Walk-Forward Window Results", header_style="bold green", border_style="dim")
    tbl.add_column("Window", justify="center", style="cyan")
    tbl.add_column("IS Range (Bars)", justify="center", style="dim")
    tbl.add_column("OOS Range (Bars)", justify="center", style="dim")
    tbl.add_column("Optimal Params (IS)", style="yellow")
    tbl.add_column("IS Sharpe", justify="right", style="bold white")
    tbl.add_column("OOS Sharpe", justify="right", style="bold green")

    for w in wf_res.windows:
        tbl.add_row(
            f"Window {w.window_index + 1}",
            f"{w.is_start} -> {w.is_end}",
            f"{w.oos_start} -> {w.oos_end}",
            str(w.best_params),
            f"{w.is_sharpe:.2f}",
            f"{w.oos_sharpe:.2f}",
        )

    console.print(tbl)

    # 5. Output Summary Card
    wfe_pct = wf_res.wfe_ratio * 100.0
    console.print(Panel.fit(
        f"[bold white]Walk-Forward Efficiency (WFE):[/bold white] [bold green]{wfe_pct:.1f}%[/bold green]\n"
        f"[bold white]Overall Stitched Out-of-Sample Sharpe:[/bold white] [bold green]{wf_res.overall_oos_sharpe:.2f}[/bold green]",
        border_style="cyan"
    ))

    # 6. Save Plot Artifact (walk_forward_dashboard.png)
    chart_path = run_dir / "walk_forward_dashboard.png"
    plot_walk_forward_dashboard(
        wf_res=wf_res,
        title="Moving Average Cross Walk-Forward Out-of-Sample Performance",
        save_path=str(chart_path),
    )
    console.print(f"[bold green][PASS] Saved Walk-Forward Dashboard Plot to:[/bold green] [bold cyan]{chart_path.resolve()}[/bold cyan]")

    # 7. Save JSON & Environment Artifacts
    wf_summary = {
        "overall_oos_sharpe": wf_res.overall_oos_sharpe,
        "wfe_ratio": wf_res.wfe_ratio,
        "num_windows": len(wf_res.windows),
        "windows": [
            {
                "window": w.window_index + 1,
                "best_params": w.best_params,
                "is_sharpe": w.is_sharpe,
                "oos_sharpe": w.oos_sharpe,
            }
            for w in wf_res.windows
        ]
    }
    with open(run_dir / "walk_forward_results.json", "w") as f:
        json.dump(wf_summary, f, indent=2)

    capture_environment_snapshot(run_dir)

    # 8. Sync 1-to-1 to artifacts/latest/
    sync_latest_run_folder(run_dir)
    console.print(f"[bold green][PASS] Synced Run Assets to Artifacts Latest Folder:[/bold green] [bold cyan]{(Path('artifacts') / 'latest').resolve()}[/bold cyan]")


if __name__ == "__main__":
    main()
