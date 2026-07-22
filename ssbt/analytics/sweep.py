"""Parameter sweep — grid search across strategy parameters.

Loads data once into InMemoryFeed, runs engine per parameter combo.
Supports parallel execution via concurrent.futures.

Usage:
    from ssbt.analytics.sweep import param_grid, run_sweep
    from ssbt.data.feed import ParquetFeed

    feed = ParquetFeed("data.parquet", symbol="BTC")
    combos = param_grid(fast_period=[5, 10, 20], slow_period=[20, 30, 50])
    results = run_sweep(SmaStrategy, feed, combos, initial_cash=100_000)
"""

from __future__ import annotations

import itertools
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

import polars as pl

from ssbt.analytics.metrics import compute_metrics
from ssbt.core.engine import BacktestResult, Engine
from ssbt.data.feed import InMemoryFeed


@dataclass(slots=True)
class SweepResult:
    params: dict
    metrics: dict
    final_equity: float
    n_trades: int


def param_grid(**kwargs) -> list[dict]:
    """Generate all parameter combinations from named lists.

    Example: param_grid(fast=[5,10], slow=[20,30]) →
        [{"fast": 5, "slow": 20}, {"fast": 5, "slow": 30}, ...]
    """
    keys = list(kwargs.keys())
    values = list(kwargs.values())
    return [dict(zip(keys, combo, strict=True)) for combo in itertools.product(*values)]


def _run_single(
    strategy_class,
    df: pl.DataFrame,
    symbol: str,
    params: dict,
    initial_cash: float,
    start: int,
    end: int,
) -> SweepResult:
    """Run a single backtest with given params. Used by run_sweep."""
    feed = InMemoryFeed(df, symbol, start, end)
    strategy = strategy_class(**params)
    engine = Engine(feed, strategy, initial_cash=initial_cash)
    result = engine.run()

    metrics = compute_metrics(result.equity_curve, result.trades)
    return SweepResult(
        params=params,
        metrics=metrics,
        final_equity=result.final_equity,
        n_trades=len(result.trades),
    )


def run_sweep(
    strategy_class,
    feed,  # ParquetFeed or InMemoryFeed
    param_combos: list[dict],
    initial_cash: float = 100_000.0,
    start: int = 0,
    end: int | None = None,
    max_workers: int | None = None,
    progress: bool = True,
) -> list[SweepResult]:
    """Run backtest for each parameter combination.

    Args:
        strategy_class: Strategy subclass to instantiate per combo.
        feed: ParquetFeed (loads DataFrame once, reuses for all combos).
        param_combos: List of param dicts from param_grid().
        initial_cash: Starting capital per run.
        start/end: Row slice for the data (walk-forward use).
        max_workers: Parallel processes. None = CPU count.
        progress: Print progress to stderr.

    Returns:
        List of SweepResult, sorted by final_equity descending.
    """
    # Extract DataFrame once — avoid re-reading Parquet
    if hasattr(feed, "to_inmemory"):
        symbol = feed.symbols[0]
        df = feed.get_dataframe(symbol)
    elif hasattr(feed, "get_dataframe"):
        symbol = feed.symbols[0]
        df = feed.get_dataframe(symbol)
    else:
        raise TypeError(f"Unsupported feed type: {type(feed)}")

    n = len(param_combos)
    if progress:
        print(f"Running {n} parameter combinations on {len(df)} bars...", flush=True)

    results: list[SweepResult] = []
    t0 = time.perf_counter()

    if max_workers == 1:
        # Sequential — faster for small sweeps (no process spawn overhead)
        for i, params in enumerate(param_combos):
            r = _run_single(strategy_class, df, symbol, params, initial_cash, start, end or len(df))
            results.append(r)
            if progress and (i + 1) % max(1, n // 10) == 0:
                elapsed = time.perf_counter() - t0
                print(f"  {i+1}/{n} done ({elapsed:.1f}s)", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_run_single, strategy_class, df, symbol, params, initial_cash, start, end or len(df)): params
                for params in param_combos
            }
            for i, future in enumerate(as_completed(futures)):
                r = future.result()
                results.append(r)
                if progress and (i + 1) % max(1, n // 10) == 0:
                    elapsed = time.perf_counter() - t0
                    print(f"  {i+1}/{n} done ({elapsed:.1f}s)", flush=True)

    elapsed = time.perf_counter() - t0
    if progress:
        print(f"Sweep complete: {n} runs in {elapsed:.2f}s ({elapsed/n:.3f}s/run)", flush=True)

    results.sort(key=lambda r: r.final_equity, reverse=True)
    return results


def best_result(results: list[SweepResult], metric: str = "final_equity") -> SweepResult:
    """Return the best SweepResult by given metric."""
    if not results:
        raise ValueError("No results torank")
    reverse = metric not in ("max_drawdown",)
    return sorted(results, key=lambda r: r.metrics.get(metric, r.final_equity), reverse=reverse)[0]


def results_to_dataframe(results: list[SweepResult]) -> pl.DataFrame:
    """Convert sweep results to a Polars DataFrame for analysis."""
    rows = []
    for r in results:
        row = dict(r.params)
        row.update(r.metrics)
        rows.append(row)
    return pl.DataFrame(rows)
