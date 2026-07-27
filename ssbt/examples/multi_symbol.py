"""Example: multi-symbol portfolio with dynamic allocation.

Run: python -m ssbt.examples.multi_symbol
"""

from __future__ import annotations

import numpy as np
import polars as pl

from ssbt import MultiSymbolEngine, ParquetFeed, Strategy
from ssbt.analytics.metrics import compute_metrics, format_metrics
from ssbt.analytics.plots import plot_equity_curve
from ssbt.portfolio.allocation import equal_weight, inverse_volatility, custom_allocation
from ssbt.core.events import Bar, Side


def generate_multi_symbol_data(n_bars=5000, seed=42):
    rng = np.random.default_rng(seed)
    ts = (np.datetime64("2023-01-01").astype("datetime64[ns]").astype(np.int64)
          + np.arange(n_bars) * 86_400_000_000_000)
    symbols = {}
    for name, start, vol, drift in [("BTC", 30000, 0.02, 0.0005), ("ETH", 2000, 0.025, 0.0003), ("SOL", 100, 0.035, 0.0008)]:
        r = rng.normal(drift, vol, n_bars)
        close = start * np.cumprod(1 + r)
        ib = np.abs(rng.normal(0, 0.01, n_bars)) * close
        symbols[name] = pl.DataFrame({
            "timestamp": ts, "open": np.roll(close, 1),
            "high": np.maximum(np.roll(close, 1), close) + ib * 0.3,
            "low": np.minimum(np.roll(close, 1), close) - ib * 0.3,
            "close": close, "volume": rng.lognormal(18, 1, n_bars),
        })
    return symbols


class MultiSymbolStrategy(Strategy):
    def __init__(self, sma_period=20):
        self.sma_period = sma_period
        self._sma, self._counts = {}, {}

    def on_init(self, engine):
        for sym in engine.symbols:
            df = engine.get_dataframe(sym)
            self._sma[sym] = df.with_columns(pl.col("close").rolling_mean(self.sma_period).alias("sma"))["sma"].to_numpy()
            self._counts[sym] = 0

    def on_bar(self, bar, engine):
        idx = self._counts.get(bar.symbol, 0)
        self._counts[bar.symbol] = idx + 1
        sma = self._sma.get(bar.symbol)
        if sma is None or idx >= len(sma) or np.isnan(sma[idx]):
            return
        pos = engine.portfolio.positions.get(bar.symbol)
        if bar.close > sma[idx] and (pos is None or pos.qty == 0):
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, 1.0))
        elif bar.close <= sma[idx] and pos and pos.qty > 0:
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, pos.qty))


def custom_alloc_fn(bars, timestamp, ctx):
    ph = ctx.get("price_history", {})
    if not ph:
        return equal_weight(bars, timestamp)
    returns = {}
    for sym in bars:
        h = ph.get(sym, [])
        returns[sym] = (h[-1] / h[-2] - 1.0) if len(h) >= 2 and h[-2] > 0 else 0.0
    pos = {s: max(r, 0.0) for s, r in returns.items()}
    total = sum(pos.values())
    return {s: v / total for s, v in pos.items()} if total > 0 else equal_weight(bars, timestamp)


def run_alloc(name, alloc_fn, feeds, rebalance_freq=5):
    engine = MultiSymbolEngine(feeds=feeds, strategy=MultiSymbolStrategy(20), allocation_fn=alloc_fn,
                               initial_cash=100_000.0, rebalance_freq=rebalance_freq)
    result = engine.run()
    metrics = compute_metrics(result.equity_curve, result.trades)
    plot_equity_curve(result.equity_curve, title=name, save_path=f"multi_{name.lower().replace(' ','_')}.png")
    return result, metrics


def main():
    print("=" * 60)
    print("Multi-Symbol Portfolio with Dynamic Allocation")
    print("=" * 60)

    data = generate_multi_symbol_data()
    feeds = {}
    for sym, df in data.items():
        path = f"{sym.lower()}_data.parquet"
        df.write_parquet(path)
        feeds[sym] = ParquetFeed(path, symbol=sym)
        print(f"  {sym}: {len(df)} bars")

    prices = {s: f.get_dataframe(s)["close"].to_list() for s, f in feeds.items()}

    results = []
    results.append(("Equal Weight", *run_alloc("Equal Weight", equal_weight, feeds)))
    results.append(("Inverse Vol", *run_alloc("Inverse Vol", inverse_volatility(prices, 20), feeds)))
    results.append(("Custom Mom", *run_alloc("Custom Mom", custom_allocation(custom_alloc_fn, price_history={}), feeds, 10)))

    print(f"\n{'Strategy':<15} {'Equity':>12} {'Return':>10} {'Sharpe':>8}")
    print(f"{'--------':<15} {'------':>12} {'------':>10} {'------':>8}")
    for name, r, m in results:
        print(f"{name:<15} {r.final_equity:>12.2f} {m['total_return']*100:>9.2f}% {m['sharpe']:>8.3f}")


if __name__ == "__main__":
    main()
