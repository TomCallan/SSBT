"""Experiment runner for the exploration engine.

Loads a YAML experiment config, resolves plugins from the registry,
executes the event/outcome pipeline, and writes artifacts.
"""

from __future__ import annotations

import json
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl

from ssbt.data.feed import ParquetFeed
from ssbt.experiments.loader import load_experiment, LoaderError
from ssbt.experiments.registry import Registry
from ssbt.experiments.stats import (
    compute_confidence_stats,
    event_count_diagnostics,
    check_leakage,
)
from ssbt.events import VolumeSpike
from ssbt.outcomes import ForwardReturn


class RunnerError(Exception):
    """Raised when the experiment runner encounters an error."""

    def __init__(self, message: str, errors: list | None = None):
        self.errors = errors or []
        super().__init__(message)


def _load_data(spec) -> pl.DataFrame:
    """Load OHLCV data from the experiment spec."""
    source = spec.dataset.source
    feed = ParquetFeed(source, symbol=spec.dataset.symbol)
    df = feed.get_dataframe()
    return df


def _build_registry() -> Registry:
    """Build a registry with built-in plugins."""
    reg = Registry()
    reg.register_event("volume_spike", VolumeSpike)
    reg.register_outcome("forward_return", ForwardReturn)
    return reg


def _run_events(df: pl.DataFrame, spec, reg: Registry) -> pl.DataFrame:
    """Run all event plugins and combine results."""
    all_events = []
    event_id_offset = 0

    for ev_spec in spec.events:
        cls = reg.get_event(ev_spec.name)
        params = ev_spec.params or {}
        instance = cls()
        events_df = instance.compute_events(df, params)

        if not events_df.is_empty():
            # Renumber event_ids to be unique across all events
            n = events_df.height
            events_df = events_df.with_columns(
                pl.Series("event_id", range(event_id_offset + 1, event_id_offset + n + 1))
            )
            event_id_offset += n

        all_events.append(events_df)

    if not all_events:
        return pl.DataFrame(schema={
            "event_id": pl.Int64,
            "timestamp": pl.Int64,
            "event_name": pl.Utf8,
            "symbol": pl.Utf8,
            "event_meta": pl.Object,
        })

    combined = pl.concat(all_events, how="vertical_relaxed")
    combined = combined.sort("timestamp")
    return combined


def _run_outcomes(df: pl.DataFrame, events: pl.DataFrame, spec, reg: Registry) -> pl.DataFrame:
    """Run all outcome plugins and combine results."""
    all_outcomes = []

    for oc_spec in spec.outcomes:
        cls = reg.get_outcome(oc_spec.name)
        params = oc_spec.params or {}
        instance = cls()
        outcomes_df = instance.compute_outcomes(df, events, params)

        if not outcomes_df.is_empty():
            all_outcomes.append(outcomes_df)

    if not all_outcomes:
        return pl.DataFrame(schema={
            "event_id": pl.Int64,
            "outcome_name": pl.Utf8,
            "horizon": pl.Int64,
            "value": pl.Float64,
            "diagnostics": pl.Object,
        })

    combined = pl.concat(all_outcomes, how="vertical_relaxed")
    return combined


def _compute_statistics(outcomes: pl.DataFrame, spec) -> dict[str, Any]:
    """Compute summary statistics per spec.analysis.statistics."""
    if outcomes.is_empty():
        return {}

    stats_config = spec.analysis.statistics if spec.analysis else None
    include = stats_config.include if stats_config else ["mean", "median", "std", "hit_rate"]
    quantiles = stats_config.quantiles if stats_config else [0.05, 0.25, 0.5, 0.75, 0.95]

    result = {}

    # Overall stats
    overall = {}
    values = outcomes["value"].to_numpy()
    if len(values) > 0:
        if "mean" in include:
            overall["mean"] = float(values.mean())
        if "median" in include:
            overall["median"] = float(np.median(values))
        if "std" in include:
            overall["std"] = float(values.std())
        if "hit_rate" in include:
            overall["hit_rate"] = float((values > 0).mean())
        if "quantiles" in include and quantiles:
            overall["quantiles"] = {f"q{int(q*100)}": float(np.quantile(values, q)) for q in quantiles}
    result["overall"] = overall

    # Per-horizon stats
    by_horizon = {}
    for h in outcomes["horizon"].unique().to_list():
        h_vals = outcomes.filter(pl.col("horizon") == h)["value"].to_numpy()
        if len(h_vals) > 0:
            h_stats = {}
            if "mean" in include:
                h_stats["mean"] = float(h_vals.mean())
            if "median" in include:
                h_stats["median"] = float(np.median(h_vals))
            if "std" in include:
                h_stats["std"] = float(h_vals.std())
            if "hit_rate" in include:
                h_stats["hit_rate"] = float((h_vals > 0).mean())
            if "quantiles" in include and quantiles:
                h_stats["quantiles"] = {f"q{int(q*100)}": float(np.quantile(h_vals, q)) for q in quantiles}
            by_horizon[str(h)] = h_stats
    result["by_horizon"] = by_horizon

    # Per-outcome_name stats
    by_outcome = {}
    for name in outcomes["outcome_name"].unique().to_list():
        o_vals = outcomes.filter(pl.col("outcome_name") == name)["value"].to_numpy()
        if len(o_vals) > 0:
            o_stats = {}
            if "mean" in include:
                o_stats["mean"] = float(o_vals.mean())
            if "median" in include:
                o_stats["median"] = float(np.median(o_vals))
            if "std" in include:
                o_stats["std"] = float(o_vals.std())
            if "hit_rate" in include:
                o_stats["hit_rate"] = float((o_vals > 0).mean())
            by_outcome[name] = o_stats
    result["by_outcome"] = by_outcome

    return result


def _write_artifacts(
    events: pl.DataFrame,
    outcomes: pl.DataFrame,
    stats: dict,
    spec,
    output_dir: Path,
):
    """Write all artifacts to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)

    formats = spec.reporting.formats if spec.reporting and spec.reporting.formats else ["csv", "json", "parquet"]

    def _drop_struct_cols(df: pl.DataFrame) -> pl.DataFrame:
        struct_cols = [c for c, dt in zip(df.columns, df.dtypes) if dt == pl.Struct]
        if struct_cols:
            return df.drop(struct_cols)
        return df

    # Events
    if "csv" in formats:
        _drop_struct_cols(events).write_csv(output_dir / "events.csv")
    if "json" in formats:
        events.write_json(output_dir / "events.json")
    if "parquet" in formats:
        events.write_parquet(output_dir / "events.parquet")

    # Outcomes
    if "csv" in formats:
        _drop_struct_cols(outcomes).write_csv(output_dir / "outcomes.csv")
    if "json" in formats:
        outcomes.write_json(output_dir / "outcomes.json")
    if "parquet" in formats:
        outcomes.write_parquet(output_dir / "outcomes.parquet")

    # Summary stats
    summary = {
        "experiment_name": spec.experiment_name,
        "experiment_type": spec.experiment_type,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "n_events": events.height,
        "n_outcomes": outcomes.height,
        "statistics": stats,
    }
    if "json" in formats:
        with open(output_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)

    # Manifest
    manifest = {
        "experiment_name": spec.experiment_name,
        "experiment_type": spec.experiment_type,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "artifacts": [
            f.name for f in output_dir.iterdir() if f.is_file()
        ],
    }
    with open(output_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


def run_experiment(config_path: str | Path) -> dict[str, Any]:
    """Run a full experiment from a YAML/JSON config file.

    Args:
        config_path: Path to the config file (.yaml, .yml, or .json).

    Returns:
        Dict with keys: events (DataFrame), outcomes (DataFrame), stats (dict), output_dir (Path)

    Raises:
        RunnerError: If config load, validation, or execution fails.
    """
    try:
        spec = load_experiment(config_path)
    except LoaderError as e:
        raise RunnerError(f"Failed to load experiment config: {e}", e.errors)

    reg = _build_registry()
    df = _load_data(spec)
    events = _run_events(df, spec, reg)
    outcomes = _run_outcomes(df, events, spec, reg)

    # Compute basic statistics
    stats = _compute_statistics(outcomes, spec)

    # Add confidence intervals if configured
    if spec.analysis and spec.analysis.confidence and spec.analysis.confidence.method == "bootstrap":
        ci_stats = compute_confidence_stats(outcomes, spec)
        if ci_stats:
            stats["confidence"] = ci_stats

    # Add event count diagnostics
    diagnostics = event_count_diagnostics(events, outcomes)
    stats["diagnostics"] = diagnostics

    # Add leakage checks
    max_horizon = 0
    if spec.outcomes:
        for oc in spec.outcomes:
            if oc.params and "horizons" in oc.params:
                max_horizon = max(max_horizon, max(oc.params["horizons"]))
    if max_horizon > 0:
        leakage = check_leakage(df, events, outcomes, max_horizon)
        stats["leakage"] = leakage

    output_dir = Path(spec.reporting.output_dir if spec.reporting else "artifacts")
    _write_artifacts(events, outcomes, stats, spec, output_dir)

    return {
        "events": events,
        "outcomes": outcomes,
        "statistics": stats,
        "output_dir": output_dir,
    }


def main() -> int:
    """CLI entry point for ssbt-run."""
    import sys
    if len(sys.argv) < 2:
        print("Usage: ssbt-run <config.yaml>", file=sys.stderr)
        return 1

    config_path = sys.argv[1]
    if not Path(config_path).exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 1

    try:
        result = run_experiment(config_path)
        print(f"Experiment completed. Events: {result['events'].height}, Outcomes: {result['outcomes'].height}")
        print(f"Artifacts written to: {result['output_dir']}")
        return 0
    except RunnerError as e:
        print(f"Experiment failed: {e}", file=sys.stderr)
        if e.errors:
            for err in e.errors:
                print(f"  - {err.path}: {err.message}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())