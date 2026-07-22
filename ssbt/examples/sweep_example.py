"""Example: parameter sweep + walk-forward optimisation.

Generates synthetic data, runs grid sweep, then walk-forward optimisation.
Run: python -m ssbt.examples.sweep_example
"""

from __future__ import annotations

import polars as pl

from ssbt.analytics.sweep import param_grid, run_sweep, results_to_dataframe
from ssbt.analytics.walkforward import walk_forward
from ssbt.data.feed import ParquetFeed
from ssbt.examples.sma_cross import SmaCrossStrategy, generate_synthetic_ohlcv


def main():
    # Generate data
    print("Generating synthetic OHLCV data...")
    df = generate_synthetic_ohlcv(n_bars=5000)
    parquet_path = "synthetic_ohlcv.parquet"
    df.write_parquet(parquet_path)
    print(f"  Wrote {len(df)} bars to {parquet_path}")

    feed = ParquetFeed(parquet_path, symbol="SYNTH")

    # === 1. Parameter Sweep ===
    print("\n" + "=" * 60)
    print("PARAMETER SWEEP")
    print("=" * 60)

    combos = param_grid(
        fast_period=[5, 10, 15, 20],
        slow_period=[20, 30, 50, 80],
        qty=[100.0],
    )
    print(f"Grid: {len(combos)} combinations")

    results = run_sweep(
        SmaCrossStrategy,
        feed,
        combos,
        initial_cash=100_000.0,
        max_workers=1,  # sequential: faster for small grids
        progress=True,
    )

    print("\nTop 5 by final equity:")
    for i, r in enumerate(results[:5]):
        print(f"  {i+1}. {r.params} -> equity={r.final_equity:.0f} "
              f"sharpe={r.metrics['sharpe']:.3f} return={r.metrics['total_return']*100:.2f}% "
              f"trades={r.n_trades}")

    # Save full results
    results_df = results_to_dataframe(results)
    results_df.write_csv("sweep_results.csv")
    print(f"\nSaved sweep_results.csv ({len(results_df)} rows)")

    # === 2. Walk-Forward Optimisation ===
    print("\n" + "=" * 60)
    print("WALK-FORWARD OPTIMISATION")
    print("=" * 60)

    wf = walk_forward(
        strategy_class=SmaCrossStrategy,
        feed=feed,
        param_grid=param_grid(
            fast_period=[5, 10, 15, 20],
            slow_period=[20, 30, 50, 80],
            qty=[100.0],
        ),
        in_sample_size=1000,
        out_sample_size=500,
        mode="rolling",
        initial_cash=100_000.0,
        progress=True,
    )

    print(f"\nWalk-forward results:")
    print(f"  Windows: {len(wf.windows)}")
    print(f"  Avg OS Sharpe: {wf.avg_os_sharpe:.4f}")
    print(f"  Avg OS Return: {wf.avg_os_return*100:.2f}%")

    print("\nPer-window breakdown:")
    for i, w in enumerate(wf.windows):
        print(f"  W{i+1}: params={w.best_params} "
              f"IS_sharpe={w.is_metrics['sharpe']:.3f} "
              f"OS_sharpe={w.os_metrics['sharpe']:.3f} "
              f"OS_ret={w.os_metrics['total_return']*100:.2f}%")

    wf_df = wf.to_dataframe()
    wf_df.write_csv("walkforward_results.csv")
    print(f"\nSaved walkforward_results.csv ({len(wf_df)} rows)")


if __name__ == "__main__":
    main()
