"""Parameter optimization — grid search, matrix sweep, walk-forward, and extensible optimizer interface.

Exports:
  - param_grid: generate cartesian product of param lists
  - run_sweep: run one backtest per param combo (auto-detects vectorised)
  - run_matrix_sweep: pack all combos into one Numba call (vectorbt-style)
  - walk_forward: IS/OS windowed optimisation
  - BaseOptimizer: ABC for custom optimizers (GA, RL, Bayesian, etc)
  - GridSearch: built-in grid search optimizer
"""

from __future__ import annotations

import itertools
import time
from abc import ABC, abstractmethod
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

import numpy as np
import polars as pl

from ssbt.analytics.metrics import compute_metrics
from ssbt.core.engine import Engine
from ssbt.core.vectorised import VectorisedBacktester, VectorisedStrategy
from ssbt.core._numba_kernels import _matrix_sweep_kernel
from ssbt.data.feed import InMemoryFeed


@dataclass(slots=True)
class SweepResult:
    params: dict
    metrics: dict
    final_equity: float
    n_trades: int


def param_grid(**kwargs) -> list[dict]:
    """Generate all parameter combinations: param_grid(fast=[5,10], slow=[20,30])."""
    keys = list(kwargs.keys())
    values = list(kwargs.values())
    return [dict(zip(keys, c, strict=True)) for c in itertools.product(*values)]


def _run_single(strategy_class, df, symbol, params, initial_cash, start, end):
    """Evaluate one param set. Auto-detects vectorised vs event-driven."""
    sliced = df.slice(start, (end or len(df)) - start)

    if issubclass(strategy_class, VectorisedStrategy):
        strategy = strategy_class(**params)
        bt = VectorisedBacktester(initial_cash=initial_cash)
        result = bt.run(sliced, strategy, symbol, qty=params.get("qty", 100.0))
        equity_curve = result["equity_curve"]
        trades = result["trades"]
        final_equity = result["final_equity"]
    else:
        feed = InMemoryFeed(sliced, symbol)
        strategy = strategy_class(**params)
        engine = Engine(feed, strategy, initial_cash=initial_cash)
        result = engine.run()
        equity_curve = result.equity_curve
        trades = result.trades
        final_equity = result.final_equity

    metrics = compute_metrics(equity_curve, trades)
    return SweepResult(params=params, metrics=metrics, final_equity=final_equity, n_trades=len(trades))


def run_matrix_sweep(
    strategy_class, df, symbol, param_combos,
    initial_cash=100_000.0, qty=100.0,
    slippage_bps=1.0, commission_bps=1.0,
):
    """Run all combos in one Numba call. Requires VectorisedStrategy.

    Packs N combos into a (N, n_bars) signal matrix, runs _matrix_sweep_kernel once.
    Returns list[SweepResult] sorted by final_equity desc.
    """
    if not issubclass(strategy_class, VectorisedStrategy):
        raise TypeError("run_matrix_sweep requires a VectorisedStrategy subclass")

    n = len(df)
    n_combos = len(param_combos)
    opens = df["open"].to_numpy().astype(np.float64)
    closes = df["close"].to_numpy().astype(np.float64)

    # Build signal matrix: (n_combos, n_bars)
    signal_matrix = np.empty((n_combos, n), dtype=np.float64)
    for c, params in enumerate(param_combos):
        strategy = strategy_class(**params)
        strategy.on_init(df)
        signal_matrix[c] = strategy.compute_signals(df)

    # Single Numba call for all combos
    equity_matrix, final_equities = _matrix_sweep_kernel(
        n, n_combos, opens, closes, signal_matrix,
        initial_cash, qty, slippage_bps, commission_bps,
    )

    # Extract per-combo results
    results = []
    ts = df["timestamp"].to_numpy().astype(np.int64)
    for c in range(n_combos):
        equity_curve = np.column_stack((ts, equity_matrix[c]))
        metrics = compute_metrics(equity_curve, [])
        results.append(SweepResult(
            params=param_combos[c], metrics=metrics,
            final_equity=float(final_equities[c]), n_trades=0,
        ))

    results.sort(key=lambda r: r.final_equity, reverse=True)
    return results


def run_sweep(
    strategy_class, feed, param_combos,
    initial_cash=100_000.0, start=0, end=None,
    max_workers=None, progress=True,
):
    """Run backtest per param combo. Uses matrix sweep for VectorisedStrategy when possible."""
    symbol = feed.symbols[0]
    df = feed.get_dataframe(symbol)
    end = end or len(df)
    n = len(param_combos)
    is_vec = issubclass(strategy_class, VectorisedStrategy)

    if progress:
        print(f"Running {n} combos on {len(df)} bars ({'matrix' if is_vec else 'event-driven'})...", flush=True)

    t0 = time.perf_counter()

    # Fast path: matrix sweep for vectorised strategies with no slicing
    if is_vec and start == 0 and end == len(df):
        results = run_matrix_sweep(strategy_class, df, symbol, param_combos, initial_cash)
    elif max_workers == 1 or n <= 1:
        results = [_run_single(strategy_class, df, symbol, p, initial_cash, start, end) for p in param_combos]
    else:
        results = []
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_run_single, strategy_class, df, symbol, p, initial_cash, start, end): p for p in param_combos}
            for f in as_completed(futures):
                results.append(f.result())

    if progress:
        elapsed = time.perf_counter() - t0
        print(f"Done: {n} runs in {elapsed:.2f}s ({elapsed/n:.4f}s/run)", flush=True)

    results.sort(key=lambda r: r.final_equity, reverse=True)
    return results


def results_to_dataframe(results: list[SweepResult]) -> pl.DataFrame:
    rows = [{**r.params, **r.metrics} for r in results]
    return pl.DataFrame(rows)


# ---- Walk-Forward ----

@dataclass(slots=True)
class WalkForwardWindow:
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
        rows = []
        for w in self.windows:
            row = {
                "os_equity": w.os_metrics.get("final_equity", 0.0),
                "os_sharpe": w.os_metrics.get("sharpe", 0.0),
                "os_return": w.os_metrics.get("total_return", 0.0),
                "is_sharpe": w.is_metrics.get("sharpe", 0.0),
                "n_trades": w.os_metrics.get("n_trades", 0),
            }
            row.update({f"param_{k}": v for k, v in w.best_params.items()})
            rows.append(row)
        return pl.DataFrame(rows)


def _generate_windows(n_bars, in_sample_size, out_sample_size, mode="rolling"):
    windows = []
    if mode == "rolling":
        s = 0
        while s + in_sample_size + out_sample_size <= n_bars:
            windows.append((s, s + in_sample_size, s + in_sample_size, s + in_sample_size + out_sample_size))
            s += out_sample_size
    elif mode == "expanding":
        s, e = 0, in_sample_size
        while e + out_sample_size <= n_bars:
            windows.append((s, e, e, e + out_sample_size))
            e += out_sample_size
    else:
        raise ValueError(f"Unknown mode: {mode}")
    return windows


def walk_forward(strategy_class, feed, param_grid, in_sample_size, out_sample_size,
                 mode="rolling", initial_cash=100_000.0, max_workers=None, progress=True):
    """Walk-forward optimisation with parallel IS sweep."""
    symbol = feed.symbols[0]
    df = feed.get_dataframe(symbol)
    n_bars = len(df)
    windows_idx = _generate_windows(n_bars, in_sample_size, out_sample_size, mode)
    if not windows_idx:
        raise ValueError(f"Not enough data: {n_bars} bars, need >= {in_sample_size + out_sample_size}")

    if progress:
        print(f"Walk-forward: {len(windows_idx)} windows, mode={mode}", flush=True)

    wf_windows = []
    for w_idx, (is_s, is_e, os_s, os_e) in enumerate(windows_idx):
        if progress:
            print(f"  Window {w_idx+1}/{len(windows_idx)}: IS[{is_s}:{is_e}] OS[{os_s}:{os_e}]", flush=True)

        if max_workers and max_workers > 1 and len(param_grid) > 1:
            with ProcessPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_run_single, strategy_class, df, symbol, p, initial_cash, is_s, is_e): p for p in param_grid}
                is_results = [f.result() for f in as_completed(futures)]
        else:
            is_results = [_run_single(strategy_class, df, symbol, p, initial_cash, is_s, is_e) for p in param_grid]

        best = max(is_results, key=lambda r: r.final_equity)
        os_result = _run_single(strategy_class, df, symbol, best.params, initial_cash, os_s, os_e)
        wf_windows.append(WalkForwardWindow(is_s, is_e, os_s, os_e, best.params, best.metrics, os_result.metrics, os_result.final_equity))

    os_sharpes = [w.os_metrics.get("sharpe", 0.0) for w in wf_windows]
    os_returns = [w.os_metrics.get("total_return", 0.0) for w in wf_windows]

    if progress:
        print(f"  Avg OS Sharpe: {sum(os_sharpes)/len(os_sharpes):.4f}", flush=True)

    return WalkForwardResult(wf_windows, sum(w.os_equity for w in wf_windows),
                             sum(os_sharpes)/len(os_sharpes) if os_sharpes else 0.0,
                             sum(os_returns)/len(os_returns) if os_returns else 0.0)


# ---- Extensible Optimizer Interface ----

class BaseOptimizer(ABC):
    """Base class for custom optimizers. Subclass and implement search().

    Call self.evaluate(params) to run a backtest and get SweepResult.
    Works with any optimization algorithm: GA, RL, Bayesian, random search, etc.

    Example:
        class MyGA(BaseOptimizer):
            def search(self):
                population = self._init_pop()
                for gen in range(50):
                    fitness = [self.evaluate(p).final_equity for p in population]
                    population = self._evolve(population, fitness)
                return self.results
    """

    def __init__(self, strategy_class, df, symbol, param_space, **kwargs):
        self.strategy_class = strategy_class
        self.df = df
        self.symbol = symbol
        self.param_space = param_space
        self.results: list[SweepResult] = []
        self.kwargs = kwargs

    @abstractmethod
    def search(self) -> list[SweepResult]:
        ...

    def evaluate(self, params: dict) -> SweepResult:
        """Evaluate one param set. Auto-detects vectorised vs event-driven."""
        r = _run_single(self.strategy_class, self.df, self.symbol, params,
                        self.kwargs.get("initial_cash", 100_000.0), 0, len(self.df))
        self.results.append(r)
        return r

    @property
    def best(self) -> SweepResult:
        if not self.results:
            raise ValueError("No results yet. Call search() first.")
        return max(self.results, key=lambda r: r.final_equity)


class GridSearch(BaseOptimizer):
    """Built-in grid search optimizer."""

    def search(self) -> list[SweepResult]:
        combos = param_grid(**self.param_space)
        is_vec = issubclass(self.strategy_class, VectorisedStrategy)
        if is_vec:
            self.results = run_matrix_sweep(
                self.strategy_class, self.df, self.symbol, combos,
                self.kwargs.get("initial_cash", 100_000.0),
            )
        else:
            self.results = [_run_single(
                self.strategy_class, self.df, self.symbol, p,
                self.kwargs.get("initial_cash", 100_000.0), 0, len(self.df)
            ) for p in combos]
        return self.results
