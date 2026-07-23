"""Vectorised backtest mode — no event loop, pure NumPy/Numba.

For strategies that only use market orders on bar close (SMA cross, RSI, momentum).
100-1000x faster than event-driven for simple strategies.

Strategy implements VectorisedStrategy.compute_signals(df) -> np.ndarray (+1/0/-1).
This class handles fill simulation, equity curve, trade tracking — all vectorised.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
import polars as pl

from ssbt.core.events import Fill, Side, Trade
from ssbt.core._numba_kernels import _vectorised_backtest_kernel, HAS_NUMBA


class VectorisedStrategy(ABC):
    """Protocol for vectorised strategies. Implement compute_signals() instead of on_bar().

    compute_signals() receives the full DataFrame, returns a signal array:
      +1 = go long
      -1 = go short
       0 = flat / no action

    The vectorised backtester handles fill simulation, position tracking, equity, trades.
    No event loop, no per-bar Python — all NumPy.
    """

    @abstractmethod
    def compute_signals(self, df: pl.DataFrame) -> np.ndarray:
        """Return signal array: +1 long, -1 short, 0 flat. One value per bar."""
        ...

    def on_init(self, df: pl.DataFrame) -> None:
        """Optional: precompute indicators on full DataFrame. Called before compute_signals."""
        pass


class VectorisedBacktester:
    """Run a vectorised backtest — no event loop, pure NumPy/Numba.

    Market orders only. Fills at next bar open. Slippage + commission as bps.

    Args:
        initial_cash: Starting capital.
        commission_bps: Commission in basis points (1 = 0.01%).
        slippage_bps: Slippage in basis points (1 = 0.01%).

    Usage:
        strategy = MyVectorisedStrategy(fast=10, slow=30)
        bt = VectorisedBacktester(initial_cash=100_000)
        result = bt.run(df, strategy, symbol="BTC", qty=100.0)
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        commission_bps: float = 1.0,
        slippage_bps: float = 1.0,
    ):
        self.initial_cash = initial_cash
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps

    def run(
        self,
        df: pl.DataFrame,
        strategy: VectorisedStrategy,
        symbol: str,
        qty: float = 100.0,
    ) -> dict:
        """Execute vectorised backtest.

        Returns dict with: equity_curve, fills, trades, final_equity, n_events.
        """
        strategy.on_init(df)

        signals = strategy.compute_signals(df)
        if len(signals) != len(df):
            raise ValueError(
                f"Signal length {len(signals)} != data length {len(df)}"
            )

        n = len(df)
        opens = df["open"].to_numpy().astype(np.float64)
        closes = df["close"].to_numpy().astype(np.float64)
        timestamps = df["timestamp"].to_numpy().astype(np.int64)

        # Run kernel
        result = _vectorised_backtest_kernel(
            n,
            opens,
            closes,
            signals.astype(np.float64),
            self.initial_cash,
            float(qty),
            self.slippage_bps,
            self.commission_bps,
        )

        equity_arr, trade_entry_idx, trade_exit_idx, trade_entry_prices, \
            trade_exit_prices, trade_qtys, trade_sides, trade_pnls, n_trades = result

        # Build equity curve
        equity_curve = np.column_stack((timestamps, equity_arr))

        # Build Trade objects
        trades: list[Trade] = []
        for i in range(n_trades):
            trades.append(Trade(
                symbol=symbol,
                entry_time=int(trade_entry_idx[i]),
                exit_time=int(trade_exit_idx[i]),
                entry_price=float(trade_entry_prices[i]),
                exit_price=float(trade_exit_prices[i]),
                qty=float(trade_qtys[i]),
                side=Side.BUY if trade_sides[i] == 1 else Side.SELL,
                pnl=float(trade_pnls[i]),
                commission=0.0,
            ))

        # Build fills (reconstructed from trades)
        fills: list[Fill] = []
        fill_id = 1
        for t in trades:
            entry_ts = int(timestamps[t.entry_time]) if t.entry_time < n else int(timestamps[-1])
            exit_ts = int(timestamps[t.exit_time]) if t.exit_time < n else int(timestamps[-1])
            fills.append(Fill(
                timestamp=entry_ts,
                order_id=fill_id,
                symbol=symbol,
                side=t.side,
                qty=t.qty,
                price=t.entry_price,
                commission=0.0,
            ))
            fill_id += 1
            fills.append(Fill(
                timestamp=exit_ts,
                order_id=fill_id,
                symbol=symbol,
                side=Side.SELL if t.side == Side.BUY else Side.BUY,
                qty=t.qty,
                price=t.exit_price,
                commission=0.0,
            ))
            fill_id += 1

        return {
            "equity_curve": equity_curve,
            "fills": fills,
            "trades": trades,
            "final_equity": float(equity_arr[-1]) if n > 0 else 0.0,
            "n_events": n,
            "_strategy": strategy,
            "_symbol": symbol,
        }

