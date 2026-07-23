"""Numba JIT kernels. Falls back to pure Python if numba not installed."""

from __future__ import annotations

import numpy as np

try:
    from numba import njit, prange
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False

    def njit(*args, **kwargs):  # type: ignore
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def decorator(fn):
            return fn
        return decorator

    def prange(*args):
        return range(*args)


@njit(cache=True)
def _vectorised_backtest_kernel(
    n_bars, opens, closes, signals,
    initial_cash, qty_per_trade, slippage_bps, commission_bps,
):
    """Single-strategy vectorised backtest. Returns equity + trade arrays."""
    equity = np.empty(n_bars, dtype=np.float64)
    cash = initial_cash
    position = 0.0
    entry_price = 0.0
    entry_idx = 0
    entry_side = 0
    slip = slippage_bps * 0.0001
    comm = commission_bps * 0.0001
    max_trades = n_bars
    trade_entry_idx = np.empty(max_trades, dtype=np.int64)
    trade_exit_idx = np.empty(max_trades, dtype=np.int64)
    trade_entry_price = np.empty(max_trades, dtype=np.float64)
    trade_exit_price = np.empty(max_trades, dtype=np.float64)
    trade_qty = np.empty(max_trades, dtype=np.float64)
    trade_side = np.empty(max_trades, dtype=np.int64)
    trade_pnl = np.empty(max_trades, dtype=np.float64)
    n_trades = 0
    prev_signal = 0

    for i in range(n_bars):
        sig = signals[i]
        o = opens[i]
        c = closes[i]
        if sig != prev_signal and sig != 0:
            if position != 0 and entry_side != 0:
                if entry_side == 1:
                    exit_price = o * (1.0 - slip)
                    pnl = (exit_price - entry_price) * abs(position)
                    cash += abs(position) * exit_price * (1.0 - comm)
                else:
                    exit_price = o * (1.0 + slip)
                    pnl = (entry_price - exit_price) * abs(position)
                    cash -= abs(position) * exit_price * (1.0 + comm)
                trade_entry_idx[n_trades] = entry_idx
                trade_exit_idx[n_trades] = i
                trade_entry_price[n_trades] = entry_price
                trade_exit_price[n_trades] = exit_price
                trade_qty[n_trades] = abs(position)
                trade_side[n_trades] = entry_side
                trade_pnl[n_trades] = pnl
                n_trades += 1
                position = 0.0
                entry_side = 0
            if sig > 0:
                fill_price = o * (1.0 + slip)
                position = qty_per_trade
                cash -= qty_per_trade * fill_price * (1.0 + comm)
                entry_price = fill_price
                entry_idx = i
                entry_side = 1
            elif sig < 0:
                fill_price = o * (1.0 - slip)
                position = -qty_per_trade
                cash += qty_per_trade * fill_price * (1.0 - comm)
                entry_price = fill_price
                entry_idx = i
                entry_side = -1
        prev_signal = sig
        equity[i] = cash + position * c if position != 0 else cash

    if position != 0 and entry_side != 0:
        c_last = closes[n_bars - 1]
        if entry_side == 1:
            exit_price = c_last * (1.0 - slip)
            pnl = (exit_price - entry_price) * abs(position)
            cash += abs(position) * exit_price * (1.0 - comm)
        else:
            exit_price = c_last * (1.0 + slip)
            pnl = (entry_price - exit_price) * abs(position)
            cash -= abs(position) * exit_price * (1.0 + comm)
        trade_entry_idx[n_trades] = entry_idx
        trade_exit_idx[n_trades] = n_bars - 1
        trade_entry_price[n_trades] = entry_price
        trade_exit_price[n_trades] = exit_price
        trade_qty[n_trades] = abs(position)
        trade_side[n_trades] = entry_side
        trade_pnl[n_trades] = pnl
        n_trades += 1
        equity[n_bars - 1] = cash

    return (equity, trade_entry_idx[:n_trades], trade_exit_idx[:n_trades],
            trade_entry_price[:n_trades], trade_exit_price[:n_trades],
            trade_qty[:n_trades], trade_side[:n_trades], trade_pnl[:n_trades], n_trades)


@njit(cache=True, parallel=True)
def _matrix_sweep_kernel(
    n_bars, n_combos,
    opens, closes, signal_matrix,
    initial_cash, qty_per_trade, slippage_bps, commission_bps,
):
    """Run N strategy configs simultaneously. Returns (n_combos, n_bars) equity matrix."""
    equity_matrix = np.empty((n_combos, n_bars), dtype=np.float64)
    final_equities = np.empty(n_combos, dtype=np.float64)

    for c in prange(n_combos):
        cash = initial_cash
        position = 0.0
        entry_price = 0.0
        prev_signal = 0
        slip = slippage_bps * 0.0001
        comm = commission_bps * 0.0001

        for i in range(n_bars):
            sig = signal_matrix[c, i]
            o = opens[i]
            cl = closes[i]

            if sig != prev_signal and sig != 0:
                if position != 0:
                    if position > 0:
                        exit_price = o * (1.0 - slip)
                        cash += abs(position) * exit_price * (1.0 - comm)
                    else:
                        exit_price = o * (1.0 + slip)
                        cash -= abs(position) * exit_price * (1.0 + comm)
                    position = 0.0

                if sig > 0:
                    fp = o * (1.0 + slip)
                    position = qty_per_trade
                    cash -= qty_per_trade * fp * (1.0 + comm)
                    entry_price = fp
                elif sig < 0:
                    fp = o * (1.0 - slip)
                    position = -qty_per_trade
                    cash += qty_per_trade * fp * (1.0 - comm)
                    entry_price = fp

            prev_signal = sig
            equity_matrix[c, i] = cash + position * cl if position != 0 else cash

        if position != 0:
            c_last = closes[n_bars - 1]
            if position > 0:
                cash += abs(position) * c_last * (1.0 - slip) * (1.0 - comm)
            else:
                cash -= abs(position) * c_last * (1.0 + slip) * (1.0 + comm)
            equity_matrix[c, n_bars - 1] = cash

        final_equities[c] = equity_matrix[c, n_bars - 1]

    return equity_matrix, final_equities
