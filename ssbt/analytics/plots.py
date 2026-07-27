"""Plotting — lazy matplotlib import. Equity curve, drawdown, trade markers."""

from __future__ import annotations

import numpy as np

from ssbt.core.events import Trade


def _import_mpl():
    """Lazy import matplotlib. Returns (plt, dates)."""
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt
    return plt


def plot_equity_curve(
    equity_curve: np.ndarray,
    title: str = "Equity Curve",
    save_path: str | None = None,
):
    """Plot equity curve over time."""
    plt = _import_mpl()
    fig, ax = plt.subplots(figsize=(12, 5))

    ts = equity_curve[:, 0]
    equity = equity_curve[:, 1]

    ax.plot(ts, equity, linewidth=0.8, color="steelblue")
    ax.fill_between(ts, equity, equity[0], alpha=0.15, color="steelblue")
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        plt.close()
        return None
    plt.show()
    return fig


def plot_drawdown(
    equity_curve: np.ndarray,
    title: str = "Drawdown",
    save_path: str | None = None,
):
    """Plot drawdown percentage over time."""
    plt = _import_mpl()
    fig, ax = plt.subplots(figsize=(12, 4))

    equity = equity_curve[:, 1]
    ts = equity_curve[:, 0]
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak * 100

    ax.fill_between(ts, drawdown, 0, color="crimson", alpha=0.4)
    ax.plot(ts, drawdown, linewidth=0.6, color="crimson")
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        plt.close()
        return None
    plt.show()
    return fig


def plot_trades(
    equity_curve: np.ndarray,
    trades: list[Trade],
    title: str = "Equity Curve with Trades",
    save_path: str | None = None,
):
    """Plot equity curve with buy/sell trade markers."""
    plt = _import_mpl()
    fig, ax = plt.subplots(figsize=(12, 5))

    ts = equity_curve[:, 0]
    equity = equity_curve[:, 1]

    ax.plot(ts, equity, linewidth=0.8, color="steelblue")
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.3)

    # Mark exit points of round-trip trades
    for t in trades:
        exit_idx = np.searchsorted(ts, t.exit_time)
        if exit_idx < len(ts):
            color = "green" if t.pnl > 0 else "red"
            marker = "^" if t.pnl > 0 else "v"
            ax.scatter(ts[exit_idx], equity[exit_idx], color=color, marker=marker, s=30, zorder=5)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        plt.close()
        return None
    plt.show()
    return fig
