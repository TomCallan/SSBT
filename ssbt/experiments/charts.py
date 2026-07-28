"""Chart generation for the exploration engine.

Generates standard visualizations for experiment results.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import polars as pl


def _save_plot(fig: plt.Figure, output_dir: Path, name: str) -> str:
    """Save plot to file and return relative path."""
    path = output_dir / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    return f"{name}.png"


def generate_distribution_chart(
    outcomes: pl.DataFrame,
    stats: dict[str, Any],
    output_dir: Path,
) -> str:
    """Generate histogram of outcome values with confidence intervals."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    axes = axes.flatten()

    # Overall distribution
    values = outcomes["value"].to_numpy()
    ax = axes[0]
    n, bins, patches = ax.hist(values, bins=50, alpha=0.7, edgecolor='black', density=True)
    ax.set_xlabel('Forward Return')
    ax.set_ylabel('Density')
    ax.set_title('Overall Distribution of Forward Returns')
    ax.axvline(0, color='red', linestyle='--', label='Zero')
    if "confidence" in stats and "overall" in stats["confidence"]:
        ci = stats["confidence"]["overall"]["mean"]
        ax.axvline(ci["estimate"], color='green', label=f'Mean ({ci["estimate"]:.4f})')
        ax.axvspan(ci["ci_lower"], ci["ci_upper"], alpha=0.2, color='green', label='95% CI')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Per-horizon distributions
    horizons = outcomes["horizon"].unique().to_list()
    for i, h in enumerate(horizons[:3]):
        ax = axes[i + 1]
        h_vals = outcomes.filter(pl.col("horizon") == h)["value"].to_numpy()
        ax.hist(h_vals, bins=30, alpha=0.7, edgecolor='black', density=True)
        ax.set_xlabel('Forward Return')
        ax.set_ylabel('Density')
        ax.set_title(f'Horizon {h}b')
        ax.axvline(0, color='red', linestyle='--')
        if "confidence" in stats and "by_horizon" in stats["confidence"]:
            ci = stats["confidence"]["by_horizon"].get(str(h), {}).get("mean")
            if ci:
                ax.axvline(ci["estimate"], color='green')
                ax.axvspan(ci["ci_lower"], ci["ci_upper"], alpha=0.2, color='green')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return _save_plot(fig, output_dir, "distribution")


def generate_grouped_bar_chart(
    outcomes: pl.DataFrame,
    stats: dict[str, Any],
    output_dir: Path,
) -> str:
    """Generate grouped bar chart of mean returns by horizon."""
    if "by_horizon" not in stats:
        return ""

    fig, ax = plt.subplots(figsize=(10, 6))

    horizons = sorted(stats["by_horizon"].keys(), key=int)
    means = [stats["by_horizon"][h].get("mean", 0) for h in horizons]
    medians = [stats["by_horizon"][h].get("median", 0) for h in horizons]

    x = np.arange(len(horizons))
    width = 0.35

    bars1 = ax.bar(x - width/2, means, width, label='Mean', color='steelblue', alpha=0.8)
    bars2 = ax.bar(x + width/2, medians, width, label='Median', color='orange', alpha=0.8)

    ax.set_xlabel('Horizon (bars)')
    ax.set_ylabel('Return')
    ax.set_title('Mean and Median Forward Returns by Horizon')
    ax.set_xticks(x)
    ax.set_xticklabels(horizons)
    ax.legend()
    ax.axhline(0, color='black', linewidth=0.5)
    ax.grid(True, alpha=0.3, axis='y')

    # Add confidence intervals if available
    if "confidence" in stats and "by_horizon" in stats["confidence"]:
        for i, h in enumerate(horizons):
            ci = stats["confidence"]["by_horizon"].get(h, {}).get("mean")
            if ci:
                ax.errorbar(i - width/2, ci["estimate"],
                           yerr=[[ci["estimate"] - ci["ci_lower"]], [ci["ci_upper"] - ci["estimate"]]],
                           fmt='none', color='black', capsize=5)

    plt.tight_layout()
    return _save_plot(fig, output_dir, "grouped_bar")


def generate_event_timeline_chart(
    events: pl.DataFrame,
    outcomes: pl.DataFrame,
    stats: dict[str, Any],
    output_dir: Path,
) -> str:
    """Generate event timeline with outcome markers."""
    if events.is_empty():
        return ""

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    # Top: Event timestamps
    event_ts = events["timestamp"].to_numpy()
    ax1.scatter(event_ts, np.ones_like(event_ts), alpha=0.6, s=20, color='blue', label=f'Events ({len(event_ts)})')
    ax1.set_ylabel('Events')
    ax1.set_title('Event Timeline')
    ax1.set_ylim(0.5, 1.5)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Bottom: Outcome values over time (event index)
    if not outcomes.is_empty():
        # Get event timestamps for each outcome
        event_ts_map = dict(zip(events["event_id"].to_list(), event_ts))
        outcome_ts = [event_ts_map.get(eid, 0) for eid in outcomes["event_id"].to_list()]
        outcome_vals = outcomes["value"].to_numpy()

        # Color by positive/negative
        colors = ['green' if v > 0 else 'red' for v in outcome_vals]
        ax2.scatter(outcome_ts, outcome_vals, c=colors, alpha=0.5, s=10)
        ax2.axhline(0, color='black', linewidth=0.5)
        ax2.set_ylabel('Forward Return')
        ax2.set_xlabel('Timestamp')
        ax2.set_title('Outcome Values by Event Time')
        ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    return _save_plot(fig, output_dir, "event_timeline")


def generate_all_charts(
    events: pl.DataFrame,
    outcomes: pl.DataFrame,
    stats: dict[str, Any],
    spec,
    output_dir: Path,
) -> dict[str, str]:
    """Generate all charts specified in reporting.charts config.

    Args:
        events: Event DataFrame.
        outcomes: Outcome DataFrame.
        stats: Statistics dictionary.
        spec: ExperimentSpec with reporting.charts list.
        output_dir: Output directory for artifacts.

    Returns:
        Dict mapping chart names to file paths.
    """
    charts_config = spec.reporting.charts if spec.reporting and spec.reporting.charts else []
    results = {}

    for chart_name in charts_config:
        try:
            if chart_name == "distribution":
                results["distribution"] = generate_distribution_chart(outcomes, stats, output_dir)
            elif chart_name == "grouped_bar":
                results["grouped_bar"] = generate_grouped_bar_chart(outcomes, stats, output_dir)
            elif chart_name == "event_timeline":
                results["event_timeline"] = generate_event_timeline_chart(events, outcomes, stats, output_dir)
        except Exception as e:
            results[chart_name] = f"ERROR: {e}"

    return results


def generate_matrix_heatmap_chart(
    matrix_df: pl.DataFrame,
    x_col: str,
    y_col: str,
    val_col: str,
    output_dir: Path,
    name: str = "test_matrix_heatmap",
) -> str:
    """Generate a performance heatmap plot comparing metrics across timeframes and tickers."""
    import pandas as pd
    pivot = matrix_df.pivot(values=val_col, index=y_col, on=x_col)
    y_labels = pivot[y_col].to_list()
    x_labels = [c for c in pivot.columns if c != y_col]
    matrix_data = pivot.select(x_labels).to_numpy()

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(matrix_data, cmap="RdYlGn", aspect="auto")

    ax.set_xticks(np.arange(len(x_labels)))
    ax.set_yticks(np.arange(len(y_labels)))
    ax.set_xticklabels(x_labels, rotation=45, ha="right")
    ax.set_yticklabels(y_labels)

    for i in range(len(y_labels)):
        for j in range(len(x_labels)):
            val = matrix_data[i, j]
            text = f"{val:.2f}" if not np.isnan(val) else "N/A"
            ax.text(j, i, text, ha="center", va="center", color="black", fontsize=9)

    ax.set_title(f"Performance Heatmap ({val_col}) Across Tickers & Timeframes")
    fig.colorbar(im, ax=ax)
    plt.tight_layout()
    return _save_plot(fig, output_dir, name)


def _to_datetime_series(timestamps: np.ndarray):
    """Convert array of timestamps (ns, ms, s) or bar indices to datetime objects or step indices."""
    import pandas as pd
    if len(timestamps) == 0:
        return timestamps
    first_val = float(timestamps[0])
    if first_val > 1e16:
        return pd.to_datetime(timestamps, unit="ns")
    elif first_val > 1e12:
        return pd.to_datetime(timestamps, unit="us")
    elif first_val > 1e10:
        return pd.to_datetime(timestamps, unit="ms")
    elif first_val > 1e7:
        return pd.to_datetime(timestamps, unit="s")
    else:
        return np.arange(len(timestamps))


def generate_multi_equity_curve_chart(
    equity_curves_dict: dict[str, np.ndarray],
    output_dir: Path,
    name: str = "multi_equity_curves",
) -> str:
    """Generate a combined multi-strategy / multi-asset equity curve comparison plot."""
    import pandas as pd
    fig, ax = plt.subplots(figsize=(12, 6))

    for label, eq_arr in equity_curves_dict.items():
        if len(eq_arr) > 0:
            x_vals = _to_datetime_series(eq_arr[:, 0])
            equities = eq_arr[:, 1]
            ax.plot(x_vals, equities, label=label, linewidth=1.8)

    ax.set_xlabel("Date / Bar Index")
    ax.set_ylabel("Account Equity ($)")
    ax.set_title("Multi-Strategy & Multi-Asset Equity Curve Comparison")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    return _save_plot(fig, output_dir, name)