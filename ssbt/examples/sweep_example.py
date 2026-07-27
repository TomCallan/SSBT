"""Example: parameter sweep + walk-forward optimisation.

Run: python -m ssbt.examples.sweep_example
"""

from ssbt import ParquetFeed, param_grid, run_sweep, walk_forward
from ssbt.analytics.optimization import results_to_dataframe
from ssbt.examples.sma_cross import SmaCrossStrategy, generate_synthetic_ohlcv


def main():
    df = generate_synthetic_ohlcv(n_bars=5000)
    df.write_parquet("synthetic_ohlcv.parquet")
    feed = ParquetFeed("synthetic_ohlcv.parquet", symbol="SYNTH")

    print("=" * 50)
    print("PARAMETER SWEEP (16 combos)")
    print("=" * 50)
    combos = param_grid(fast_period=[5, 10, 15, 20], slow_period=[20, 30, 50, 80], qty=[100.0])
    results = run_sweep(SmaCrossStrategy, feed, combos, max_workers=1)
    print("\nTop 5:")
    for i, r in enumerate(results[:5]):
        print(f"  {i+1}. {r.params} -> equity={r.final_equity:.0f} sharpe={r.metrics['sharpe']:.3f}")
    results_to_dataframe(results).write_csv("sweep_results.csv")

    print("\n" + "=" * 50)
    print("WALK-FORWARD OPTIMISATION")
    print("=" * 50)
    wf = walk_forward(SmaCrossStrategy, feed, combos, in_sample_size=1000, out_sample_size=500, mode="rolling")
    print(f"\nWindows: {len(wf.windows)} | Avg OS Sharpe: {wf.avg_os_sharpe:.4f} | Avg OS Return: {wf.avg_os_return*100:.2f}%")
    for i, w in enumerate(wf.windows):
        print(f"  W{i+1}: {w.best_params} OS_sharpe={w.os_metrics['sharpe']:.3f} OS_ret={w.os_metrics['total_return']*100:.2f}%")
    wf.to_dataframe().write_csv("walkforward_results.csv")


if __name__ == "__main__":
    main()
