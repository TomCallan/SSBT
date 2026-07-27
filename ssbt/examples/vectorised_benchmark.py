"""Example: vectorised vs event-driven benchmark + RSI strategy.

Run: python -m ssbt.examples.vectorised_benchmark
"""

from __future__ import annotations

import time
import numpy as np
import polars as pl

from ssbt import ParquetFeed, Engine, Strategy, VectorisedStrategy, VectorisedBacktester
from ssbt.analytics.optimization import param_grid, run_sweep
from ssbt.analytics.metrics import compute_metrics, format_metrics
from ssbt.core.events import Bar, Side
from ssbt.examples.sma_cross import SmaCrossStrategy, generate_synthetic_ohlcv


class SmaCrossVectorised(VectorisedStrategy):
    def __init__(self, fast_period=10, slow_period=30, qty=100.0):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.qty = qty

    def compute_signals(self, df):
        df = df.with_columns([
            pl.col("close").rolling_mean(self.fast_period).alias("sf"),
            pl.col("close").rolling_mean(self.slow_period).alias("ss"),
        ])
        f, s = df["sf"].to_numpy(), df["ss"].to_numpy()
        sig = np.zeros(len(f))
        v = ~(np.isnan(f) | np.isnan(s))
        sig[v] = np.where(f[v] > s[v], 1.0, -1.0)
        return sig


class RsiVectorised(VectorisedStrategy):
    def __init__(self, period=14, oversold=30.0, overbought=70.0, qty=100.0):
        self.period, self.oversold, self.overbought, self.qty = period, oversold, overbought, qty

    def compute_signals(self, df):
        close = df["close"].to_numpy()
        n = len(close)
        signals = np.zeros(n)
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.zeros(n)
        avg_loss = np.zeros(n)
        if n > self.period:
            avg_gain[self.period] = np.mean(gains[:self.period])
            avg_loss[self.period] = np.mean(losses[:self.period])
            for i in range(self.period + 1, n):
                avg_gain[i] = (avg_gain[i-1] * (self.period - 1) + gains[i-1]) / self.period
                avg_loss[i] = (avg_loss[i-1] * (self.period - 1) + losses[i-1]) / self.period
            with np.errstate(divide='ignore', invalid='ignore'):
                rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100.0)
            rsi = 100.0 - (100.0 / (1.0 + rs))
            rsi[:self.period] = 50.0
            for i in range(1, n):
                if rsi[i] < self.oversold and rsi[i-1] >= self.oversold:
                    signals[i] = 1.0
                elif rsi[i] > self.overbought and rsi[i-1] <= self.overbought:
                    signals[i] = -1.0
                else:
                    signals[i] = signals[i-1]
        return signals


def main():
    n_bars = 50000
    print(f"Generating {n_bars} bars...")
    df = generate_synthetic_ohlcv(n_bars=n_bars)
    df.write_parquet("synthetic_ohlcv.parquet")
    feed = ParquetFeed("synthetic_ohlcv.parquet", symbol="SYNTH")

    # Event-driven
    t0 = time.perf_counter()
    r_ed = Engine(feed, SmaCrossStrategy(10, 30, 100.0), initial_cash=100_000.0).run()
    t_ed = time.perf_counter() - t0
    m_ed = compute_metrics(r_ed.equity_curve, r_ed.trades)
    print(f"\nEvent-driven:  {t_ed:.4f}s ({n_bars/t_ed:,.0f} bars/sec) | equity={r_ed.final_equity:.0f} trades={len(r_ed.trades)}")

    # Vectorised
    bt = VectorisedBacktester(initial_cash=100_000.0)
    t0 = time.perf_counter()
    r_vec = bt.run(df, SmaCrossVectorised(10, 30), "SYNTH", qty=100.0)
    t_vec = time.perf_counter() - t0
    m_vec = compute_metrics(r_vec["equity_curve"], r_vec["trades"])
    print(f"Vectorised:    {t_vec:.4f}s ({n_bars/t_vec:,.0f} bars/sec) | equity={r_vec['final_equity']:.0f} trades={len(r_vec['trades'])}")
    print(f"Speedup:       {n_bars/t_vec / (n_bars/t_ed):.1f}x")

    # RSI (vectorised)
    t0 = time.perf_counter()
    r_rsi = bt.run(df, RsiVectorised(14, 30, 70), "SYNTH", qty=100.0)
    t_rsi = time.perf_counter() - t0
    m_rsi = compute_metrics(r_rsi["equity_curve"], r_rsi["trades"])
    print(f"\nRSI strategy:  {t_rsi:.4f}s ({n_bars/t_rsi:,.0f} bars/sec)")
    print(format_metrics(m_rsi))

    # Matrix sweep (64 combos, one Numba call)
    combos = param_grid(fast_period=[3,5,8,10,15,20,25,30], slow_period=[10,20,30,40,50,70,100,150], qty=[100.0])
    print(f"\nMatrix sweep: {len(combos)} combos...")
    t0 = time.perf_counter()
    results = run_sweep(SmaCrossVectorised, feed, combos, max_workers=1, progress=True)
    t_sweep = time.perf_counter() - t0
    print(f"\nTop 3: (sweep in {t_sweep:.2f}s)")
    for i, r in enumerate(results[:3]):
        print(f"  {i+1}. fast={r.params['fast_period']} slow={r.params['slow_period']} "
              f"-> equity={r.final_equity:>10.0f} sharpe={r.metrics['sharpe']:.3f}")


if __name__ == "__main__":
    main()
