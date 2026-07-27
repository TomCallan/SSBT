"""Volume spike event detection plugin.

Detects bars where volume exceeds a multiple of the recent average volume.
"""

from __future__ import annotations

import polars as pl

from ssbt.events.base import BaseEvent, REQUIRED_EVENT_COLUMNS


class VolumeSpike(BaseEvent):
    """Detect volume spikes relative to a rolling average.

    Parameters (from config):
        window: int = 20        -- lookback window for average volume
        multiplier: float = 2.0 -- volume must exceed avg * multiplier
        min_volume: float = 0   -- absolute minimum volume to consider
    """

    name = "volume_spike"
    api_version = 1

    def compute_events(self, df: pl.DataFrame, params: dict) -> pl.DataFrame:
        # Validate required columns
        required = {"timestamp", "volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Input DataFrame missing required columns: {missing}")

        window = params.get("window", 20)
        multiplier = params.get("multiplier", 2.0)
        min_volume = params.get("min_volume", 0)

        # Compute rolling average volume
        df_with_avg = df.with_columns(
            pl.col("volume").rolling_mean(window).alias("avg_volume")
        )

        # Identify spikes
        df_with_spikes = df_with_avg.with_columns(
            is_spike=(
                (pl.col("volume") > pl.col("avg_volume") * multiplier)
                & (pl.col("volume") >= min_volume)
            )
        )

        # Extract spike events
        spike_df = df_with_spikes.filter(pl.col("is_spike"))

        if spike_df.is_empty():
            return pl.DataFrame(
                schema={
                    "event_id": pl.Int64,
                    "timestamp": pl.Int64,
                    "event_name": pl.Utf8,
                    "symbol": pl.Utf8,
                    "event_meta": pl.Object,
                }
            )

        # Build event table - collect to Python lists to avoid Expr issues
        timestamps = spike_df["timestamp"].to_list()
        volumes = spike_df["volume"].to_list()
        avg_volumes = spike_df["avg_volume"].to_list()
        n = len(timestamps)
        event_ids = list(range(1, n + 1))

        result = pl.DataFrame({
            "event_id": event_ids,
            "timestamp": timestamps,
            "event_name": [self.name] * n,
            "symbol": [""] * n,
            "event_meta": [
                {
                    "volume": float(volumes[i]),
                    "avg_volume": float(avg_volumes[i]),
                    "multiplier": multiplier,
                    "ratio": float(volumes[i] / avg_volumes[i]) if avg_volumes[i] > 0 else 0.0,
                }
                for i in range(n)
            ],
        })

        # Validate output schema
        BaseEvent.check_event_table(result)
        return result

    def validate_params(self, params: dict) -> list[str]:
        errs = []
        if "window" in params and not isinstance(params["window"], int):
            errs.append("window must be an integer")
        if "multiplier" in params and not isinstance(params["multiplier"], (int, float)):
            errs.append("multiplier must be a number")
        if params.get("window", 20) < 1:
            errs.append("window must be >= 1")
        if params.get("multiplier", 2.0) <= 0:
            errs.append("multiplier must be > 0")
        return errs