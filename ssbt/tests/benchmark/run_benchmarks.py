"""Extreme scale benchmark suite runner for SSBT.

Evaluates throughput across:
- Compiled Vectorized Numba Strategy vs. Complex Non-Compiled Python Strategy
- 10 Million JIT-generated 1-min bars
- Parquet Feed
- Synthetic WebSocket LiveStreamFeed
"""

import time
import threading
from pathlib import Path
import numpy as np
import polars as pl
from rich.console import Console
from rich.table import Table

from ssbt import (
    Engine, Strategy, Side, OrderType, OrderStatus,
    InMemoryFeed, ParquetFeed, LiveStreamFeed,
    VectorisedBacktester, VectorisedStrategy,
)
from ssbt.tests.benchmark.test_extreme_scale_benchmark import (
    VectorisedSMAStrategy, LeanSMAStrategy, ComplexPythonStrategy, _generate_synthetic_bar_df,
)


def run_benchmark_suite(scale_10m: bool = True):
    console = Console()
    console.print("\n[bold cyan]=======================================================[/bold cyan]")
    console.print("[bold yellow]      SSBT EXTREME SCALE BENCHMARK PERFORMANCE MATRIX     [/bold yellow]")
    console.print("[bold cyan]=======================================================[/bold cyan]\n")

    results = []

    # 1. Vectorised Numba Strategy (10M Bars)
    n_bars_10m = 10_000_000 if scale_10m else 1_000_000
    console.print(f"Generating [bold green]{n_bars_10m:,}[/bold green] bars in-memory via NumPy JIT...")
    df_10m = _generate_synthetic_bar_df(n_bars_10m)

    vec_strat = VectorisedSMAStrategy(period=20)
    vec_bt = VectorisedBacktester(initial_cash=100_000.0)

    t0 = time.perf_counter()
    res_vec = vec_bt.run(df_10m, vec_strat, symbol="SYNTH")
    t1 = time.perf_counter()
    dur_vec = t1 - t0
    rate_vec = n_bars_10m / dur_vec
    results.append(("Vectorised Numba (Compiled)", "JIT In-Memory Feed", f"{n_bars_10m:,}", f"{dur_vec:.4f}s", f"{rate_vec:,.0f} bars/sec", f"{1.0/rate_vec*1e6:.3f} µs"))

    # 2. Fast Bar Engine — Event-Driven (1M Bars)
    n_bars_1m = 1_000_000
    df_1m = df_10m.slice(0, n_bars_1m) if len(df_10m) >= n_bars_1m else _generate_synthetic_bar_df(n_bars_1m)
    feed_mem = InMemoryFeed(df_1m, symbol="SYNTH")

    lean_strat = LeanSMAStrategy(period=20)
    engine_fast = Engine(feed=feed_mem, strategy=lean_strat, initial_cash=100_000.0)

    t0 = time.perf_counter()
    res_fast = engine_fast.run()
    t1 = time.perf_counter()
    dur_fast = t1 - t0
    rate_fast = n_bars_1m / dur_fast
    results.append(("Fast Bar Engine (Event-Driven)", "JIT InMemoryFeed", f"{n_bars_1m:,}", f"{dur_fast:.4f}s", f"{rate_fast:,.0f} bars/sec", f"{1.0/rate_fast*1e6:.3f} µs"))

    # 3. Complex Non-Compiled Python Strategy (1M Bars)
    complex_strat = ComplexPythonStrategy(lookback=50)
    feed_mem2 = InMemoryFeed(df_1m, symbol="SYNTH")
    engine_complex = Engine(feed=feed_mem2, strategy=complex_strat, initial_cash=100_000.0)

    t0 = time.perf_counter()
    res_complex = engine_complex.run()
    t1 = time.perf_counter()
    dur_complex = t1 - t0
    rate_complex = n_bars_1m / dur_complex
    results.append(("Complex Non-Compiled Python", "JIT InMemoryFeed", f"{n_bars_1m:,}", f"{dur_complex:.4f}s", f"{rate_complex:,.0f} bars/sec", f"{1.0/rate_complex*1e6:.3f} µs"))

    # 4. Parquet Stream Feed (500,000 Bars)
    n_bars_pq = 500_000
    df_pq = df_1m.slice(0, n_bars_pq)
    pq_path = Path("tmp_bench_stream.parquet")
    df_pq.write_parquet(pq_path)

    pq_feed = ParquetFeed(str(pq_path), symbol="SYNTH")
    engine_pq = Engine(feed=pq_feed, strategy=LeanSMAStrategy(period=20), initial_cash=100_000.0)

    t0 = time.perf_counter()
    res_pq = engine_pq.run()
    t1 = time.perf_counter()
    dur_pq = t1 - t0
    rate_pq = n_bars_pq / dur_pq
    results.append(("Fast Bar Engine (Event-Driven)", "Disk ParquetFeed", f"{n_bars_pq:,}", f"{dur_pq:.4f}s", f"{rate_pq:,.0f} bars/sec", f"{1.0/rate_pq*1e6:.3f} µs"))

    if pq_path.exists():
        pq_path.unlink()

    # 5. Synthetic WebSocket LiveStreamFeed (200,000 Ticks)
    n_ticks_ws = 200_000
    live_feed = LiveStreamFeed(symbols="SYNTH", timeout=0.1)

    def producer():
        prices = 100.0 + np.cumsum(np.random.randn(n_ticks_ws) * 0.05)
        timestamps = np.arange(n_ticks_ws, dtype=np.int64) * 1_000_000
        for i in range(n_ticks_ws):
            live_feed.push_bidask(
                timestamp=int(timestamps[i]),
                symbol="SYNTH",
                bid=float(prices[i] - 0.05),
                ask=float(prices[i] + 0.05),
            )
        live_feed.stop()

    prod_thread = threading.Thread(target=producer)
    engine_ws = Engine(feed=live_feed, strategy=LeanSMAStrategy(period=20), initial_cash=100_000.0)

    t0 = time.perf_counter()
    prod_thread.start()
    res_ws = engine_ws.run()
    prod_thread.join()
    t1 = time.perf_counter()
    dur_ws = t1 - t0
    rate_ws = n_ticks_ws / dur_ws
    results.append(("Event-Driven Engine", "WebSocket LiveStreamFeed", f"{n_ticks_ws:,}", f"{dur_ws:.4f}s", f"{rate_ws:,.0f} ticks/sec", f"{1.0/rate_ws*1e6:.3f} µs"))

    # Build Rich Table
    table = Table(title="SSBT Extreme Benchmark Results", show_header=True, header_style="bold magenta")
    table.add_column("Strategy Engine Mode", style="cyan")
    table.add_column("Data Source / Feed", style="green")
    table.add_column("Events Processed", justify="right", style="yellow")
    table.add_column("Total Time", justify="right")
    table.add_column("Throughput", justify="right", style="bold green")
    table.add_column("Avg Latency", justify="right", style="dim")

    for r in results:
        table.add_row(*r)

    console.print(table)
    console.print("\n[bold green]Extreme Scale Benchmark Complete![/bold green]\n")


if __name__ == "__main__":
    run_benchmark_suite(scale_10m=True)
