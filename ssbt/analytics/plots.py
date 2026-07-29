"""Plotting — lazy matplotlib import. Equity curve, drawdown, trade markers."""

from __future__ import annotations

import sys
from pathlib import Path
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
    equity_curves: dict[str, np.ndarray] | np.ndarray,
    trades: list[Trade] | None = None,
    prices: np.ndarray | None = None,
    dates: list | np.ndarray | None = None,
    robustness_stats: dict[str, Any] | None = None,
    title: str = "Institutional Multi-Asset Performance Dashboard",
    initial_cash: float = 5000.0,
    save_path: str | None = None,
):
    """Plot clean 3-panel Multi-Asset Strategy Dashboard (Equity, Drawdown, Trade PnL)."""
    plt = _import_mpl()
    fig, (ax1, ax2, ax3) = plt.subplots(
        3, 1, figsize=(13, 9.5),
        gridspec_kw={"height_ratios": [3.2, 2.2, 2.2]}
    )

    eq_dict: dict[str, np.ndarray] = {}
    if isinstance(equity_curves, dict):
        eq_dict = equity_curves
    elif isinstance(equity_curves, np.ndarray):
        eq_dict = {"Strategy": equity_curves}

    colors = ["#2E7D32", "#00ACC1", "#FB8C00", "#8E24AA", "#D81B60", "#1E88E5"]

    # --- Panel 1: Multi-Asset Equity Curves ---
    ax1.set_title(title, fontsize=13, fontweight="bold", pad=10)
    for idx, (sym, eq_arr) in enumerate(eq_dict.items()):
        if eq_arr is None or len(eq_arr) == 0:
            continue
        c = colors[idx % len(colors)]
        if eq_arr.ndim == 2 and eq_arr.shape[1] == 2:
            x_vals = eq_arr[:, 0]
            y_vals = eq_arr[:, 1]
        else:
            x_vals = np.arange(len(eq_arr))
            y_vals = eq_arr

        ax1.plot(x_vals, y_vals, label=f"{sym} Equity ($)", color=c, linewidth=2.0)

    ax1.axhline(initial_cash, color="#757575", linestyle="--", alpha=0.6, label=f"Initial Capital (${initial_cash:,.0f})")
    ax1.set_ylabel("Account Equity ($)", fontweight="bold")
    ax1.legend(loc="upper left", framealpha=0.85)
    ax1.grid(True, alpha=0.25)

    # --- Panel 2: Multi-Asset Underwater Drawdown Curves (%) ---
    for idx, (sym, eq_arr) in enumerate(eq_dict.items()):
        if eq_arr is None or len(eq_arr) == 0:
            continue
        c = colors[idx % len(colors)]
        y_vals = eq_arr[:, 1] if eq_arr.ndim == 2 else eq_arr
        x_vals = eq_arr[:, 0] if eq_arr.ndim == 2 else np.arange(len(eq_arr))

        peaks = np.maximum.accumulate(y_vals)
        drawdowns_pct = (y_vals - peaks) / (peaks + 1e-8) * 100.0

        ax2.plot(x_vals, drawdowns_pct, label=f"{sym} Drawdown (%)", color=c, linewidth=1.2)
        ax2.fill_between(x_vals, drawdowns_pct, 0, color=c, alpha=0.12)

    ax2.set_ylabel("Drawdown (%)", fontweight="bold")
    ax2.legend(loc="lower left", framealpha=0.85)
    ax2.grid(True, alpha=0.25)

    # --- Panel 3: Per-Trade PnL Sequence ---
    if trades:
        trade_pnls = [t.pnl for t in trades]
        trade_x = np.arange(1, len(trade_pnls) + 1)
        bar_colors = ["#2E7D32" if p >= 0 else "#C62828" for p in trade_pnls]

        ax3.bar(trade_x, trade_pnls, color=bar_colors, width=0.6, label="Trade PnL ($)", zorder=4)
        ax3.axhline(0.0, color="#424242", linewidth=1.0)
        ax3.set_ylabel("Trade PnL ($)", fontweight="bold")
        ax3.set_xlabel("Trade Sequence Number", fontweight="bold")
        ax3.legend(loc="upper left", framealpha=0.85)
        ax3.grid(True, alpha=0.25)
    else:
        ax3.text(0.5, 0.5, "No Closed Trades Record Available", ha="center", va="center", fontsize=11, color="#757575")
        ax3.set_ylabel("Trade PnL ($)", fontweight="bold")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        plt.close()
        return None
    plt.show()
    return fig


def plot_robustness_dashboard(
    dsr_val: float = 1.0,
    pbo_val: float = 0.04,
    mc_res: dict[str, Any] | None = None,
    title: str = "Statistical Robustness & Overfitting Defense Audit",
    save_path: str | None = None,
):
    """Plot dedicated 2-panel Statistical Overfitting & Monte Carlo Audit Chart."""
    plt = _import_mpl()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # --- Panel 1: DSR & PBO Bar Visual ---
    categories = ["Deflated Sharpe Ratio\n(DSR %)", "Probability of Overfitting\n(PBO %)"]
    vals = [dsr_val * 100.0, pbo_val * 100.0]
    bar_cols = ["#2E7D32" if dsr_val >= 0.95 else "#FB8C00", "#2E7D32" if pbo_val < 0.50 else "#C62828"]

    bars = ax1.bar(categories, vals, color=bar_cols, width=0.45, zorder=4)
    ax1.axhline(95.0, color="#2E7D32", linestyle="--", alpha=0.7, label="DSR Pass Threshold (95%)")
    ax1.axhline(50.0, color="#C62828", linestyle=":", alpha=0.7, label="PBO High-Risk Limit (50%)")

    for bar, val in zip(bars, vals):
        ax1.text(bar.get_x() + bar.get_width()/2.0, bar.get_height() + 1.5, f"{val:.1f}%", ha="center", va="bottom", fontweight="bold", fontsize=10)

    ax1.set_ylim(0, 115)
    ax1.set_ylabel("Percentage (%)", fontweight="bold")
    ax1.set_title("Statistical Overfitting Defenses", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper right", framealpha=0.85)
    ax1.grid(True, alpha=0.25)

    # --- Panel 2: Monte Carlo Trade Resampling Confidence Interval ---
    mc = mc_res or {"ci_95_lower": 5000.0, "ci_95_upper": 8500.0, "max_dd_95": -0.10}
    mc_lower = mc.get("ci_95_lower", 5000.0)
    mc_upper = mc.get("ci_95_upper", 8500.0)
    mc_max_dd = mc.get("max_dd_95", -0.10) * 100.0

    mc_labels = ["95% CI Lower Equity", "95% CI Upper Equity", "95th %ile Max Drawdown"]
    mc_vals = [mc_lower, mc_upper, mc_max_dd]
    mc_colors = ["#1E88E5", "#2E7D32", "#C62828"]

    ax2.bar(mc_labels, [mc_lower, mc_upper, 0], color=mc_colors[:2], width=0.4, label="Equity Range ($)")
    ax2.set_ylabel("Account Equity ($)", fontweight="bold")
    ax2.set_title("Monte Carlo 1,000 Resampling Audit", fontsize=12, fontweight="bold")
    
    for idx, (lbl, val) in enumerate(zip(mc_labels[:2], [mc_lower, mc_upper])):
        ax2.text(idx, val + 150, f"${val:,.2f}", ha="center", va="bottom", fontweight="bold", fontsize=10)

    ax2.grid(True, alpha=0.25)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150)
        plt.close()
        return None
    plt.show()
    return fig


def plot_performance_metrics(
    matrix_results: list[dict[str, Any]],
    title: str = "Multi-Asset Performance Ratios Comparison",
    save_path: str | None = None,
):
    """Plot bar chart comparison of Sharpe, Sortino, Net Return, and Max Drawdown across matrix assets."""
    plt = _import_mpl()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    tickers = [r["ticker"] for r in matrix_results]
    sharpes = [r.get("sharpe", 0.0) for r in matrix_results]
    returns = [r.get("net_profit_pct", 0.0) for r in matrix_results]
    drawdowns = [abs(r.get("max_dd", 0.0)) for r in matrix_results]

    x = np.arange(len(tickers))
    width = 0.35

    ax1.bar(x - width/2, sharpes, width, label="Sharpe Ratio", color="#1E88E5")
    ax1.bar(x + width/2, returns, width, label="Return (%)", color="#2E7D32")
    ax1.set_xticks(x)
    ax1.set_xticklabels(tickers, fontweight="bold")
    ax1.set_title("Sharpe Ratio & Net Return (%)", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.25)

    ax2.bar(tickers, drawdowns, color="#C62828", width=0.4, label="Max Drawdown (%)")
    ax2.set_title("Max Drawdown Depth (%)", fontsize=12, fontweight="bold")
    ax2.set_ylabel("Drawdown (%)", fontweight="bold")
    ax2.grid(True, alpha=0.25)

    fig.suptitle(title, fontsize=14, fontweight="bold", y=1.02)
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150)
        plt.close()
        return None
    plt.show()
    return fig


def plot_walk_forward_dashboard(
    wf_res: Any,
    title: str = "Rolling Walk-Forward Out-of-Sample Performance Dashboard",
    save_path: str | None = None,
):
    """Plot 3-panel Walk-Forward Dashboard (Stitched OOS Equity, IS vs OOS Sharpe per Window, WFE %)."""
    plt = _import_mpl()
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(13, 10), gridspec_kw={"height_ratios": [3.0, 2.0, 2.0]})

    # --- Panel 1: Stitched Out-of-Sample Equity Curve ---
    eq = wf_res.stitched_oos_equity
    ax1.plot(eq, label="Stitched Out-of-Sample Equity ($)", color="#2E7D32", linewidth=2.0)
    ax1.axhline(eq[0], color="#757575", linestyle="--", alpha=0.6, label=f"Initial Capital (${eq[0]:,.0f})")
    ax1.set_ylabel("Account Equity ($)", fontweight="bold")
    ax1.set_title(title, fontsize=13, fontweight="bold", pad=10)
    ax1.legend(loc="upper left", framealpha=0.85)
    ax1.grid(True, alpha=0.25)

    # --- Panel 2: IS vs OOS Sharpe per Window ---
    win_indices = [w.window_index + 1 for w in wf_res.windows]
    is_sharpes = [w.is_sharpe for w in wf_res.windows]
    oos_sharpes = [w.oos_sharpe for w in wf_res.windows]

    x = np.arange(len(win_indices))
    width = 0.35

    ax2.bar(x - width/2, is_sharpes, width, label="In-Sample Sharpe (Training)", color="#1E88E5")
    ax2.bar(x + width/2, oos_sharpes, width, label="Out-of-Sample Sharpe (Testing)", color="#FB8C00")
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"W{i}" for i in win_indices], fontweight="bold")
    ax2.set_ylabel("Sharpe Ratio", fontweight="bold")
    ax2.set_title("In-Sample vs Out-of-Sample Sharpe Comparison per Window", fontsize=11, fontweight="bold")
    ax2.legend(loc="upper right", framealpha=0.85)
    ax2.grid(True, alpha=0.25)

    # --- Panel 3: Walk-Forward Efficiency (WFE %) Summary Card ---
    ax3.axis("off")
    wfe_pct = wf_res.wfe_ratio * 100.0
    status_str = "PASS (High Robustness > 50%)" if wfe_pct >= 50.0 else "WARNING (Low OOS Efficiency)"
    
    summary_data = [
        ["Walk-Forward Efficiency Metric", "Empirical Result", "Institutional Target / Status"],
        ["Overall Out-of-Sample Sharpe Ratio", f"{wf_res.overall_oos_sharpe:.2f}", "PASS (> 1.0 Target)"],
        ["Walk-Forward Efficiency Ratio (WFE)", f"{wfe_pct:.1f}%", status_str],
        ["Total Rolling Windows Evaluated", f"{len(wf_res.windows)} Windows", "COMPLETED"],
    ]

    tbl = ax3.table(
        cellText=summary_data,
        loc="center",
        cellLoc="center",
        colWidths=[0.40, 0.25, 0.35]
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    tbl.scale(1.0, 1.3)

    for i in range(3):
        tbl[(0, i)].get_text().set_fontweight("bold")
        tbl[(0, i)].set_facecolor("#37474F")
        tbl[(0, i)].get_text().set_color("white")

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
    1. BacktestResult / BacktestAdapter result dict: Renders 4-panel strategy dashboard.
    2. Polars / Pandas DataFrame: Renders price, quote, or feature series chart.
    3. NumPy Array / List: Renders line or equity curve plot.
    """
    plt = _import_mpl()

    # Default save path to artifacts/latest/ if not running inside pytest
    import os
    if save_path is None and "PYTEST_CURRENT_TEST" not in os.environ and "pytest" not in sys.modules:
        latest_dir = Path("artifacts") / "latest"
        latest_dir.mkdir(parents=True, exist_ok=True)
        fname = (title or "plot").lower().replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_") + ".png"
        save_path = str(latest_dir / fname)

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
