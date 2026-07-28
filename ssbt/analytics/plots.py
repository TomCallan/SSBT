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


def plot_strategy_dashboard(
    prices: np.ndarray,
    equity_curve: np.ndarray,
    trades: list[Trade],
    dates: list | np.ndarray | None = None,
    title: str = "Institutional Strategy Performance Dashboard",
    initial_cash: float = 5000.0,
    save_path: str | None = None,
):
    """Plot complete 4-panel Institutional Strategy Performance Dashboard.
    
    Panel 1: Price Chart + Indicator Overlays + Trade Entry/Exit Markers
    Panel 2: Account Equity Curve vs Buy-and-Hold Benchmark
    Panel 3: Underwater Drawdown Area Fill Chart (%)
    Panel 4: Per-Trade PnL Distribution Bars
    """
    plt = _import_mpl()
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(
        4, 1, figsize=(14, 12), sharex=True,
        gridspec_kw={"height_ratios": [3, 2, 1.5, 1.5]}
    )

    n_bars = len(prices)
    x_axis = dates if dates is not None and len(dates) == n_bars else np.arange(n_bars)

    # --- Panel 1: Price & Entry/Exit Markers ---
    ax1.plot(x_axis, prices, label="Asset Price ($)", color="#1E88E5", linewidth=1.5)
    
    # Calculate 20-period EMA overlay
    if n_bars >= 20:
        ema_20 = np.convolve(prices, np.ones(20)/20, mode="valid")
        ema_x = x_axis[19:]
        ax1.plot(ema_x, ema_20, label="EMA(20)", color="#FFC107", linestyle="--", linewidth=1.2)

    # Plot Trade Entry & Exit Markers
    for t in trades:
        e_idx = min(int(t.entry_time), n_bars - 1)
        x_idx = min(int(t.exit_time), n_bars - 1)
        
        entry_x = x_axis[e_idx]
        exit_x = x_axis[x_idx]
        
        ax1.scatter(entry_x, prices[e_idx], color="#2E7D32", marker="^", s=90, zorder=6, label="Buy Long" if "Buy Long" not in ax1.get_legend_handles_labels()[1] else "")
        ax1.scatter(exit_x, prices[x_idx], color="#C62828", marker="v", s=90, zorder=6, label="Sell Exit" if "Sell Exit" not in ax1.get_legend_handles_labels()[1] else "")

    ax1.set_ylabel("Price ($)", fontweight="bold")
    ax1.set_title(title, fontsize=14, fontweight="bold", pad=10)
    ax1.legend(loc="upper left", framealpha=0.8)
    ax1.grid(True, alpha=0.25)

    # --- Panel 2: Account Equity vs Buy & Hold ---
    ts_eq = equity_curve[:, 0]
    equity_vals = equity_curve[:, 1]
    eq_x = dates[:len(equity_vals)] if dates is not None and len(dates) >= len(equity_vals) else np.arange(len(equity_vals))

    bnh_equity = initial_cash * (prices[:len(equity_vals)] / prices[0])
    
    ax2.plot(eq_x, equity_vals, label="Strategy Account Equity ($)", color="#2E7D32", linewidth=2.0)
    ax2.fill_between(eq_x, equity_vals, initial_cash, color="#2E7D32", alpha=0.12)
    ax2.plot(eq_x, bnh_equity, label="Buy & Hold Benchmark ($)", color="#757575", linestyle=":", linewidth=1.5)
    ax2.axhline(initial_cash, color="#757575", linestyle="--", alpha=0.5, label=f"Initial Capital (${initial_cash:,.0f})")
    
    ax2.set_ylabel("Account Equity ($)", fontweight="bold")
    ax2.legend(loc="upper left", framealpha=0.8)
    ax2.grid(True, alpha=0.25)

    # --- Panel 3: Underwater Drawdown Chart (%) ---
    peaks = np.maximum.accumulate(equity_vals)
    drawdowns_pct = (equity_vals - peaks) / peaks * 100.0

    ax3.fill_between(eq_x, drawdowns_pct, 0, color="#C62828", alpha=0.35, label="Drawdown Depth (%)")
    ax3.plot(eq_x, drawdowns_pct, color="#C62828", linewidth=1.0)
    ax3.set_ylabel("Drawdown (%)", fontweight="bold")
    ax3.legend(loc="lower left", framealpha=0.8)
    ax3.grid(True, alpha=0.25)

    # --- Panel 4: Per-Trade PnL Bar Chart ($) ---
    if trades:
        trade_exit_indices = [min(int(t.exit_time), n_bars - 1) for t in trades]
        trade_exit_x = [x_axis[i] for i in trade_exit_indices]
        trade_pnls = [t.pnl for t in trades]
        bar_colors = ["#2E7D32" if p >= 0 else "#C62828" for p in trade_pnls]

        ax4.bar(trade_exit_x, trade_pnls, color=bar_colors, width=1.5, label="Trade PnL ($)", zorder=4)
        ax4.axhline(0.0, color="#424242", linewidth=1.0)

    ax4.set_ylabel("Trade PnL ($)", fontweight="bold")
    ax4.set_xlabel("Time", fontweight="bold")
    ax4.legend(loc="upper left", framealpha=0.8)
    ax4.grid(True, alpha=0.25)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        plt.close()
        return None
    plt.show()
    return fig


def plot(data: any, title: str | None = None, save_path: str | None = None):
    """Universal 1-line visual plotting engine for SSBT.
    
    Accepts:
    - BacktestResult / BacktestAdapter result dict: Renders 4-panel strategy dashboard.
    - Polars / Pandas DataFrame: Renders price or quote series chart.
    - NumPy Array / List: Renders line or equity curve plot.
    """
    plt = _import_mpl()

    # 1. Option A: Backtest Result Dictionary / Raw BacktestResult
    if isinstance(data, dict) and "raw_result" in data:
        raw_res = data["raw_result"]
        prices = data["feed_df"]["close"].to_numpy() if "feed_df" in data and "close" in data["feed_df"].columns else np.array([e[1] for e in raw_res.equity_curve])
        return plot_strategy_dashboard(
            prices=prices,
            equity_curve=raw_res.equity_curve,
            trades=raw_res.trades,
            title=title or "Strategy Backtest Performance Dashboard",
            save_path=save_path,
        )

    # 2. Option B: Polars / Pandas DataFrame
    elif hasattr(data, "columns"):
        cols = set(data.columns)
        fig, ax = plt.subplots(figsize=(12, 5))
        
        if "close" in cols:
            y_vals = data["close"].to_numpy() if hasattr(data["close"], "to_numpy") else np.array(data["close"])
            ax.plot(y_vals, label="Close Price ($)", color="#1E88E5", linewidth=1.5)
        elif "bid" in cols and "ask" in cols:
            b_vals = data["bid"].to_numpy() if hasattr(data["bid"], "to_numpy") else np.array(data["bid"])
            a_vals = data["ask"].to_numpy() if hasattr(data["ask"], "to_numpy") else np.array(data["ask"])
            ax.plot(b_vals, label="Bid", color="#2E7D32")
            ax.plot(a_vals, label="Ask", color="#C62828")
        else:
            first_col = list(data.columns)[0]
            y_vals = data[first_col].to_numpy() if hasattr(data[first_col], "to_numpy") else np.array(data[first_col])
            ax.plot(y_vals, label=str(first_col), color="#1E88E5")

        ax.set_title(title or "Market Data Chart", fontsize=12, fontweight="bold")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150)
            plt.close()
            return None
        plt.show()
        return fig

    # 3. Option C: NumPy Array or List
    elif isinstance(data, (np.ndarray, list)):
        arr = np.asarray(data)
        if arr.ndim == 2 and arr.shape[1] == 2:
            return plot_equity_curve(arr, title=title or "Equity Curve", save_path=save_path)
        else:
            fig, ax = plt.subplots(figsize=(12, 4))
            ax.plot(arr, color="#1E88E5", linewidth=1.5)
            ax.set_title(title or "Data Series Chart")
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            if save_path:
                plt.savefig(save_path, dpi=150)
                plt.close()
                return None
            plt.show()
            return fig


def autoplot(func):
    """Decorator that automatically plots the result returned by a function."""
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        plot(res)
        return res
    return wrapper


# Backward compatibility alias
plot_tradingview_dashboard = plot_strategy_dashboard
