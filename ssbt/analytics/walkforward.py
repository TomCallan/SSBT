"""Walk-forward optimisation — split data into IS/OS windows, optimise on IS, test on OS.

Two modes:
  - "rolling": fixed-width IS + OS windows, slide forward by OS size.
  - "expanding": IS window grows, OS window fixed.

Usage:
    from ssbt.analytics.walkforward import walk_forward, WalkForwardResult

    wf = walk_forward(
        strategy_class=SmaCrossStrategy,
        feed=feed,
        param_grid=param_grid(fast=[5,10,20], slow=[20,30,50]),
        in_sample_size=1000,
        out_sample_size=500,
        mode="rolling",
    )
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from ssbt.analytics.metrics import compute_metrics
from ssbt.analytics.sweep import SweepResult, _run_single
from ssbt.data.feed import ParquetFeed


@dataclass(slots=True)
class WalkForwardWindow:
    """One IS/OS window pair."""
    is_start: int
    is_end: int
    os_start: int
    os_end: int
    best_params: dict
    is_metrics: dict
    os_metrics: dict
    os_equity: float


@dataclass(slots=True)
class WalkForwardResult:
    windows: list[WalkForwardWindow]
    total_os_equity: float
    avg_os_sharpe: float
    avg_os_return: float

    def to_dataframe(self) -> pl.DataFrame:
        """Convert walk-forward results to a Polars DataFrame."""
        rows = []
        for w in self.windows:
            row = {
                "is_start": w.is_start,
                "is_end": w.is_end,
                "os_start": w.os_start,
                "os_end": w.os_end,
                "os_equity": w.os_metrics.get("final_equity", 0.0),
                "os_sharpe": w.os_metrics.get("sharpe", 0.0),
                "os_return": w.os_metrics.get("total_return", 0.0),
                "os_max_dd": w.os_metrics.get("max_drawdown", 0.0),
                "is_sharpe": w.is_metrics.get("sharpe", 0.0),
                "is_return": w.is_metrics.get("total_return", 0.0),
                "n_trades": w.os_metrics.get("n_trades", 0),
            }
            row.update({f"param_{k}": v for k, v in w.best_params.items()})
            rows.append(row)
        return pl.DataFrame(rows)


def _generate_windows(
    n_bars: int,
    in_sample_size: int,
    out_sample_size: int,
    mode: str = "rolling",
) -> list[tuple[int, int, int, int]]:
    """Generate (is_start, is_end, os_start, os_end) tuples."""
    windows = []
    if mode == "rolling":
        is_start = 0
        while is_start + in_sample_size + out_sample_size <= n_bars:
            is_end = is_start + in_sample_size
            os_start = is_end
            os_end = os_start + out_sample_size
            windows.append((is_start, is_end, os_start, os_end))
            is_start += out_sample_size  # slide forward by OS size
    elif mode == "expanding":
        is_start = 0
        is_end = in_sample_size
        while is_end + out_sample_size <= n_bars:
            os_start = is_end
            os_end = os_start + out_sample_size
            windows.append((is_start, is_end, os_start, os_end))
            is_end += out_sample_size  # IS window grows
    else:
        raise ValueError(f"Unknown mode: {mode}. Use 'rolling' or 'expanding'.")
    return windows


def walk_forward(
    strategy_class,
    feed: ParquetFeed,
    param_grid: list[dict],
    in_sample_size: int,
    out_sample_size: int,
    mode: str = "rolling",
    initial_cash: float = 100_000.0,
    max_workers: int | None = None,
    progress: bool = True,
) -> WalkForwardResult:
    """Run walk-forward optimisation.

    For each window:
      1. Optimise params on in-sample (IS) — pick best by final equity
      2. Test best params on out-of-sample (OS)
      3. Record IS + OS metrics

    Args:
        strategy_class: Strategy subclass.
        feed: ParquetFeed with data.
        param_grid: List of param dicts from sweep.param_grid().
        in_sample_size: Number of bars for in-sample optimisation.
        out_sample_size: Number of bars for out-of-sample testing.
        mode: "rolling" (fixed IS window slides) or "expanding" (IS grows).
        initial_cash: Starting capital per run.
        max_workers: Parallel processes for IS sweep (per window).
        progress: Print progress.

    Returns:
        WalkForwardResult with per-window results + aggregate stats.
    """
    # Extract DataFrame once
    symbol = feed.symbols[0]
    df = feed.get_dataframe(symbol)
    n_bars = len(df)

    windows_idx = _generate_windows(n_bars, in_sample_size, out_sample_size, mode)

    if not windows_idx:
        raise ValueError(
            f"Not enough data: {n_bars} bars, need >= {in_sample_size + out_sample_size}"
        )

    if progress:
        print(f"Walk-forward: {len(windows_idx)} windows, mode={mode}", flush=True)
        print(f"  IS={in_sample_size} bars, OS={out_sample_size} bars", flush=True)
        print(f"  {len(param_grid)} param combos per IS window", flush=True)

    wf_windows: list[WalkForwardWindow] = []

    for w_idx, (is_s, is_e, os_s, os_e) in enumerate(windows_idx):
        if progress:
            print(f"  Window {w_idx+1}/{len(windows_idx)}: IS[{is_s}:{is_e}] OS[{os_s}:{os_e}]", flush=True)

        # 1. Sweep on IS
        is_results: list[SweepResult] = []
        for params in param_grid:
            r = _run_single(strategy_class, df, symbol, params, initial_cash, is_s, is_e)
            is_results.append(r)

        # Pick best by final equity
        best = max(is_results, key=lambda r: r.final_equity)

        # 2. Test on OS with best params
        os_result = _run_single(strategy_class, df, symbol, best.params, initial_cash, os_s, os_e)

        wf_windows.append(WalkForwardWindow(
            is_start=is_s,
            is_end=is_e,
            os_start=os_s,
            os_end=os_e,
            best_params=best.params,
            is_metrics=best.metrics,
            os_metrics=os_result.metrics,
            os_equity=os_result.final_equity,
        ))

    # Aggregate OS stats
    os_sharpes = [w.os_metrics.get("sharpe", 0.0) for w in wf_windows]
    os_returns = [w.os_metrics.get("total_return", 0.0) for w in wf_windows]
    total_os_eq = sum(w.os_equity for w in wf_windows)

    if progress:
        print(f"\nWalk-forward complete: {len(wf_windows)} windows", flush=True)
        print(f"  Avg OS Sharpe: {sum(os_sharpes)/len(os_sharpes):.4f}", flush=True)
        print(f"  Avg OS Return: {sum(os_returns)/len(os_returns)*100:.2f}%", flush=True)

    return WalkForwardResult(
        windows=wf_windows,
        total_os_equity=total_os_eq,
        avg_os_sharpe=sum(os_sharpes) / len(os_sharpes) if os_sharpes else 0.0,
        avg_os_return=sum(os_returns) / len(os_returns) if os_returns else 0.0,
    )
