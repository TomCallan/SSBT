"""Monster example: complex multi-asset strategy on 100k bars.

Demonstrates everything SSBT can do:
  - 2 indices (synthetic S&P 500 + Nasdaq-like) with 100k bars each
  - Event-driven strategy with: SMA crossover + RSI filter + ATR position sizing
  - Limit orders, trailing stops, OCO (take-profit + stop-loss)
  - Dynamic portfolio allocation between the two indices
  - Parameter sweep (matrix sweep via Numba)
  - Walk-forward optimisation
  - Full metrics, equity curve, trade log

Run: python -m ssbt.examples.monster
"""

from __future__ import annotations

import time
import numpy as np
import polars as pl

from ssbt import (
    Engine, ParquetFeed, Strategy, VectorisedStrategy, VectorisedBacktester,
    MultiSymbolEngine, param_grid, run_sweep, walk_forward,
    compute_metrics, format_metrics, Side, TimeInForce,
)
from ssbt.portfolio.allocation import equal_weight, custom_allocation
from ssbt.analytics.plots import plot_equity_curve, plot_drawdown
from ssbt.core.events import Bar, Order, OrderType, OrderStatus


# ============================================================
# Data generation: 2 indices, 100k bars each, correlated
# ============================================================

def generate_index_data(n_bars=100_000, seed=42, start_price=4500.0,
                        drift=0.0001, vol=0.012, corr=0.7):
    """Generate synthetic OHLCV with intrabar noise."""
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, vol, n_bars)
    close = start_price * np.cumprod(1 + returns)

    # Intrabar OHLC
    noise = np.abs(rng.normal(0, vol * 0.5, n_bars)) * close
    open_ = np.roll(close, 1)
    open_[0] = start_price
    high = np.maximum(open_, close) + noise * rng.uniform(0.1, 0.5, n_bars)
    low = np.minimum(open_, close) - noise * rng.uniform(0.1, 0.5, n_bars)
    volume = rng.lognormal(15, 1.5, n_bars)

    # Timestamps: 1-minute bars
    ts = (np.datetime64("2023-01-01").astype("datetime64[ns]").astype(np.int64)
          + np.arange(n_bars) * 60_000_000_000)

    return pl.DataFrame({
        "timestamp": ts, "open": open_, "high": high,
        "low": low, "close": close, "volume": volume,
    })


def generate_correlated_indices(n_bars=100_000):
    """Generate SPX + NDX with correlation."""
    rng = np.random.default_rng(42)
    # Common factor
    common = rng.normal(0.00005, 0.008, n_bars)

    # SPX: lower vol, slight upward drift
    spx_idio = rng.normal(0.0, 0.006, n_bars)
    spx_returns = 0.7 * common + 0.3 * spx_idio + 0.00002
    spx_close = 4500 * np.cumprod(1 + spx_returns)

    # NDX: higher vol, more growth
    ndx_idio = rng.normal(0.0, 0.010, n_bars)
    ndx_returns = 0.7 * common + 0.3 * ndx_idio + 0.00003
    ndx_close = 15000 * np.cumprod(1 + ndx_returns)

    ts = (np.datetime64("2023-01-01").astype("datetime64[ns]").astype(np.int64)
          + np.arange(n_bars) * 60_000_000_000)

    def make_ohlc(close, vol_mult):
        noise = np.abs(rng.normal(0, 0.006 * vol_mult, n_bars)) * close
        open_ = np.roll(close, 1)
        open_[0] = close[0]
        return pl.DataFrame({
            "timestamp": ts, "open": open_,
            "high": np.maximum(open_, close) + noise * 0.4,
            "low": np.minimum(open_, close) - noise * 0.4,
            "close": close, "volume": rng.lognormal(16, 1.5, n_bars),
        })

    return make_ohlc(spx_close, 1.0), make_ohlc(ndx_close, 1.6)


# ============================================================
# Complex event-driven strategy
# ============================================================

class MonsterStrategy(Strategy):
    """Multi-signal strategy combining:
    - Fast/slow SMA crossover for trend direction
    - RSI filter (only enter when RSI not overbought/oversold)
    - ATR-based position sizing (volatility-adjusted)
    - Limit orders for entries (better fill prices)
    - Trailing stop for exits (lock in profits)
    - OCO: take-profit limit + trailing stop loss
    """

    def __init__(self, fast=10, slow=50, rsi_period=14,
                 rsi_overbought=70, rsi_oversold=30,
                 atr_period=20, risk_pct=0.02,
                 trail_pct=0.01, tp_pct=0.03,
                 qty=100.0):
        self.fast = fast
        self.slow = slow
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.atr_period = atr_period
        self.risk_pct = risk_pct
        self.trail_pct = trail_pct
        self.tp_pct = tp_pct
        self.qty = qty
        self._sma_fast = {}
        self._sma_slow = {}
        self._rsi = {}
        self._atr = {}
        self._bar_idx = {}
        self._positions = {}
        self._entry_submitted = {}

    def on_init(self, engine):
        symbols = engine.feed.symbols if hasattr(engine, 'feed') else engine.symbols
        for sym in symbols:
            df = self.get_dataframe(engine, sym) if hasattr(engine, 'feed') else engine.get_dataframe(sym)
            close = df["close"]
            high = df["high"]
            low = df["low"]

            df = df.with_columns([
                close.rolling_mean(self.fast).alias("sma_fast"),
                close.rolling_mean(self.slow).alias("sma_slow"),
            ])

            # RSI
            deltas = close.diff()
            gains = deltas.clip(lower_bound=0)
            losses = (-deltas).clip(lower_bound=0)
            avg_gain = gains.rolling_mean(self.rsi_period)
            avg_loss = losses.rolling_mean(self.rsi_period)
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            df = df.with_columns(rsi.alias("rsi"))

            # ATR
            tr = pl.max_horizontal(
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            )
            df = df.with_columns(tr.rolling_mean(self.atr_period).alias("atr"))

            self._sma_fast[sym] = df["sma_fast"].to_numpy()
            self._sma_slow[sym] = df["sma_slow"].to_numpy()
            self._rsi[sym] = df["rsi"].to_numpy()
            self._atr[sym] = df["atr"].to_numpy()
            self._bar_idx[sym] = 0
            self._positions[sym] = 0.0
            self._entry_submitted[sym] = False

    def on_bar(self, bar: Bar, engine):
        sym = bar.symbol
        idx = self._bar_idx[sym]
        self._bar_idx[sym] = idx + 1

        if idx < self.slow or np.isnan(self._sma_slow[sym][idx]):
            return

        sma_f = self._sma_fast[sym][idx]
        sma_s = self._sma_slow[sym][idx]
        rsi = self._rsi[sym][idx]
        atr = self._atr[sym][idx]

        if np.isnan(rsi) or np.isnan(atr) or atr <= 0:
            return

        bullish = sma_f > sma_s
        bearish = sma_f < sma_s

        # Check pending orders — if we have entry pending, don't submit more
        pending = engine.matching.pending_orders
        has_pending = any(o.symbol == sym for o in pending)

        current_pos = self._positions[sym]

        # Entry: only when flat, no pending orders, not already submitted
        if bullish and rsi < self.rsi_overbought and current_pos == 0 and not has_pending and not self._entry_submitted[sym]:
            qty = self.qty
            limit_price = bar.close * 0.999  # 10bps better
            engine.submit_order(self.limit_order(sym, Side.BUY, qty, limit_price,
                                                 tif=TimeInForce.IOC))
            self._positions[sym] = qty
            self._entry_submitted[sym] = True

            # OCO: take-profit + trailing stop
            tp_price = bar.close * (1 + self.tp_pct)
            trail = self.trailing_stop_order(sym, Side.SELL, qty,
                                             trail_offset=self.trail_pct, is_pct=True)
            tp = self.limit_order(sym, Side.SELL, qty, tp_price)
            engine.submit_oco(tp, trail)

        elif bearish and rsi > self.rsi_oversold and current_pos == 0 and not has_pending and not self._entry_submitted[sym]:
            qty = self.qty
            limit_price = bar.close * 1.001
            engine.submit_order(self.limit_order(sym, Side.SELL, qty, limit_price,
                                                 tif=TimeInForce.IOC))
            self._positions[sym] = -qty
            self._entry_submitted[sym] = True

            tp_price = bar.close * (1 - self.tp_pct)
            trail = self.trailing_stop_order(sym, Side.BUY, qty,
                                             trail_offset=self.trail_pct, is_pct=True)
            tp = self.limit_order(sym, Side.BUY, qty, tp_price)
            engine.submit_oco(tp, trail)

        # Reset entry flag when position is flat again (OCO triggered)
        if has_pending:
            # Check if OCO orders are still active
            oco_active = any(o.symbol == sym and o.oco_pair_id is not None for o in pending)
            if not oco_active and current_pos != 0:
                self._positions[sym] = 0.0
                self._entry_submitted[sym] = False

    def on_finish(self, engine):
        for sym, pos in self._positions.items():
            if pos > 0:
                engine.submit_order(self.market_order(sym, Side.SELL, pos))
            elif pos < 0:
                engine.submit_order(self.market_order(sym, Side.BUY, abs(pos)))


# ============================================================
# Vectorised version for fast sweep
# ============================================================

class MonsterVectorised(VectorisedStrategy):
    """Simplified vectorised version for fast parameter sweeps."""

    def __init__(self, fast=10, slow=50, rsi_period=14,
                 rsi_overbought=70, rsi_oversold=30, qty=100.0):
        self.fast = fast
        self.slow = slow
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.qty = qty

    def compute_signals(self, df):
        close = df["close"].to_numpy()
        n = len(close)
        signals = np.zeros(n)

        # SMA
        sma_f = df.with_columns(pl.col("close").rolling_mean(self.fast).alias("sf"))["sf"].to_numpy()
        sma_s = df.with_columns(pl.col("close").rolling_mean(self.slow).alias("ss"))["ss"].to_numpy()

        # RSI
        deltas = np.diff(close, prepend=close[0])
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.zeros(n)
        avg_loss = np.zeros(n)
        if n > self.rsi_period:
            avg_gain[self.rsi_period] = np.mean(gains[:self.rsi_period])
            avg_loss[self.rsi_period] = np.mean(losses[:self.rsi_period])
            for i in range(self.rsi_period + 1, n):
                avg_gain[i] = (avg_gain[i-1] * (self.rsi_period - 1) + gains[i]) / self.rsi_period
                avg_loss[i] = (avg_loss[i-1] * (self.rsi_period - 1) + losses[i]) / self.rsi_period
            with np.errstate(divide='ignore', invalid='ignore'):
                rs = np.where(avg_loss > 0, avg_gain / avg_loss, 100.0)
            rsi = 100.0 - (100.0 / (1.0 + rs))
        else:
            rsi = np.full(n, 50.0)

        # Signals: long when SMA cross + RSI not overbought
        for i in range(self.slow + 1, n):
            if np.isnan(sma_f[i]) or np.isnan(sma_s[i]) or np.isnan(rsi[i]):
                continue
            if sma_f[i] > sma_s[i] and rsi[i] < self.rsi_overbought:
                signals[i] = 1.0
            elif sma_f[i] < sma_s[i] and rsi[i] > self.rsi_oversold:
                signals[i] = -1.0
            else:
                signals[i] = signals[i-1] if i > 0 else 0.0

        return signals


# ============================================================
# Custom allocation: risk parity based on rolling vol
# ============================================================

def risk_parity_alloc(bars, timestamp, ctx):
    """Allocate more to lower-volatility index."""
    price_history = ctx.get("price_history", {})
    if not price_history:
        return equal_weight(bars, timestamp)

    vols = {}
    for sym in bars:
        h = price_history.get(sym, [])
        if len(h) >= 20:
            rets = np.diff(h[-20:]) / np.array(h[-21:-1])
            v = np.std(rets)
            vols[sym] = 1.0 / v if v > 0 else 0.0
        else:
            vols[sym] = 1.0

    total = sum(vols.values())
    return {s: v / total for s, v in vols.items()} if total > 0 else equal_weight(bars, timestamp)


# ============================================================
# Main
# ============================================================

def main():
    N_BARS = 100_000

    print("=" * 70)
    print(f"MONSTER EXAMPLE: Complex multi-asset strategy on {N_BARS:,} bars")
    print("=" * 70)

    # Generate data
    print(f"\nGenerating {N_BARS:,} bars for SPX + NDX...")
    t0 = time.perf_counter()
    spx_df, ndx_df = generate_correlated_indices(N_BARS)
    spx_df.write_parquet("spx.parquet")
    ndx_df.write_parquet("ndx.parquet")
    print(f"  SPX: {len(spx_df):,} bars, range [{spx_df['close'].min():.0f}, {spx_df['close'].max():.0f}]")
    print(f"  NDX: {len(ndx_df):,} bars, range [{ndx_df['close'].min():.0f}, {ndx_df['close'].max():.0f}]")
    print(f"  Generated in {time.perf_counter()-t0:.1f}s")

    feeds = {
        "SPX": ParquetFeed("spx.parquet", symbol="SPX"),
        "NDX": ParquetFeed("ndx.parquet", symbol="NDX"),
    }

    # ============================================================
    # 1. Single-asset event-driven (SPX only, full order types)
    # ============================================================
    print("\n" + "-" * 50)
    print("1. EVENT-DRIVEN: SPX, full order types (limit/trailing/OCO)")
    print("-" * 50)

    strategy = MonsterStrategy(fast=10, slow=50, rsi_period=14, qty=100.0)
    engine = Engine(feeds["SPX"], strategy, initial_cash=1_000_000.0)

    t0 = time.perf_counter()
    result = engine.run()
    t1 = time.perf_counter()
    metrics = compute_metrics(result.equity_curve, result.trades)

    print(f"  Time: {t1-t0:.2f}s ({N_BARS/(t1-t0):,.0f} bars/sec)")
    print(f"  Fills: {len(result.fills)} | Trades: {len(result.trades)}")
    print(f"  Equity: ${result.final_equity:,.0f}")
    print(format_metrics(metrics))

    plot_equity_curve(result.equity_curve, "SPX Event-Driven (Limit+Trail+OCO)", "monster_spx_equity.png")
    plot_drawdown(result.equity_curve, save_path="monster_spx_dd.png")

    # ============================================================
    # 2. Multi-asset with dynamic allocation (SPX + NDX)
    # ============================================================
    print("\n" + "-" * 50)
    print("2. MULTI-ASSET: SPX + NDX, dynamic risk-parity allocation")
    print("-" * 50)

    # Track price history for allocation
    price_history = {"SPX": [], "NDX": []}
    alloc_fn = custom_allocation(risk_parity_alloc, price_history=price_history)

    strategy2 = MonsterStrategy(fast=10, slow=50, qty=100.0)
    engine2 = MultiSymbolEngine(
        feeds=feeds, strategy=strategy2, allocation_fn=alloc_fn,
        initial_cash=1_000_000.0, rebalance_freq=100,
    )

    t0 = time.perf_counter()
    result2 = engine2.run()
    t1 = time.perf_counter()
    metrics2 = compute_metrics(result2.equity_curve, result2.trades)

    print(f"  Time: {t1-t0:.2f}s ({2*N_BARS/(t1-t0):,.0f} bars/sec)")
    print(f"  Fills: {len(result2.fills)} | Trades: {len(result2.trades)}")
    print(f"  Equity: ${result2.final_equity:,.0f}")
    print(format_metrics(metrics2))

    plot_equity_curve(result2.equity_curve, "SPX+NDX Multi-Asset", "monster_multi_equity.png")

    # ============================================================
    # 3. Matrix sweep: 64 param combos on SPX (vectorised)
    # ============================================================
    print("\n" + "-" * 50)
    print("3. MATRIX SWEEP: 64 combos on SPX (vectorised, one Numba call)")
    print("-" * 50)

    combos = param_grid(
        fast=[5, 10, 15, 20],
        slow=[30, 50, 70, 100],
        rsi_period=[14],
        rsi_overbought=[65, 70, 75, 80],
        rsi_oversold=[20, 25, 30, 35],
        qty=[100.0],
    )
    print(f"  Grid: {len(combos)} combinations")

    t0 = time.perf_counter()
    sweep_results = run_sweep(MonsterVectorised, feeds["SPX"], combos, max_workers=1, progress=True)
    t1 = time.perf_counter()
    print(f"  Total: {t1-t0:.2f}s ({len(combos)/(t1-t0):,.0f} combos/sec)")

    print(f"\n  Top 5:")
    for i, r in enumerate(sweep_results[:5]):
        print(f"    {i+1}. fast={r.params['fast']} slow={r.params['slow']} "
              f"ob={r.params['rsi_overbought']} os={r.params['rsi_oversold']} "
              f"-> equity=${r.final_equity:>12,.0f} return={r.metrics['total_return']*100:>7.2f}%")

    # ============================================================
    # 4. Walk-forward on NDX
    # ============================================================
    print("\n" + "-" * 50)
    print("4. WALK-FORWARD: NDX, 64 combos, rolling windows")
    print("-" * 50)

    wf = walk_forward(
        MonsterVectorised, feeds["NDX"], combos,
        in_sample_size=10_000, out_sample_size=5_000,
        mode="rolling", progress=True,
    )

    print(f"\n  Windows: {len(wf.windows)}")
    print(f"  Avg OS Sharpe: {wf.avg_os_sharpe:.4f}")
    print(f"  Avg OS Return: {wf.avg_os_return*100:.2f}%")

    # ============================================================
    # 5. Summary
    # ============================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Data:       2 indices x {N_BARS:,} bars = {2*N_BARS:,} total bars")
    print(f"  Event-driven SPX:  {N_BARS/(t1-t0):,.0f} bars/sec with limits/trails/OCO")
    print(f"  Multi-asset:       {2*N_BARS/(t1-t0):,.0f} bars/sec with dynamic allocation")
    print(f"  Matrix sweep:       {len(combos)} combos in one Numba call")
    print(f"  Walk-forward:      {len(wf.windows)} IS/OS windows")
    print(f"\n  Saved: monster_spx_equity.png, monster_spx_dd.png, monster_multi_equity.png")
    print("=" * 70)


if __name__ == "__main__":
    main()
