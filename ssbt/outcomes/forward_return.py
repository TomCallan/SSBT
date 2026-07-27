"""Forward return outcome plugin for the exploration engine.

Computes forward returns at specified horizons for each event.
"""

from __future__ import annotations

import polars as pl

from ssbt.outcomes.base import BaseOutcome, REQUIRED_OUTCOME_COLUMNS


class ForwardReturn(BaseOutcome):
    """Compute forward returns for each event at given horizons.

    Params:
        horizons: list of bar offsets (e.g. [1, 5, 20])
    """

    name = "forward_return"
    api_version = 1

    def compute_outcomes(
        self, df: pl.DataFrame, events: pl.DataFrame, params: dict
    ) -> pl.DataFrame:
        horizons = params.get("horizons", [1, 5, 20])

        if events.is_empty():
            return pl.DataFrame(schema={
                "event_id": pl.Int64,
                "outcome_name": pl.Utf8,
                "horizon": pl.Int64,
                "value": pl.Float64,
                "diagnostics": pl.Object,
            })

        if "close" not in df.columns:
            raise ValueError("OHLCV DataFrame must have 'close' column")

        # Map event_id -> event timestamp index in df
        df_indexed = df.with_row_index(name="_row_idx")

        events_with_idx = events.join(
            df_indexed.select(["timestamp", "_row_idx"]),
            on="timestamp",
            how="left",
        )

        # Build outcome rows
        rows = []
        for row in events_with_idx.iter_rows(named=True):
            event_id = row["event_id"]
            event_idx = row["_row_idx"]

            if event_idx is None:
                for h in horizons:
                    rows.append({
                        "event_id": event_id,
                        "outcome_name": self.name,
                        "horizon": h,
                        "value": 0.0,
                        "diagnostics": {"event_not_in_data": True},
                    })
                continue

            event_close = df["close"][event_idx]

            for h in horizons:
                future_idx = event_idx + h
                if future_idx >= len(df):
                    rows.append({
                        "event_id": event_id,
                        "outcome_name": self.name,
                        "horizon": h,
                        "value": 0.0,
                        "diagnostics": {"insufficient_future_bars": h},
                    })
                else:
                    future_close = df["close"][future_idx]
                    ret = (future_close - event_close) / event_close if event_close > 0 else 0.0
                    rows.append({
                        "event_id": event_id,
                        "outcome_name": self.name,
                        "horizon": h,
                        "value": ret,
                        "diagnostics": {"ok": True},
                    })

        if not rows:
            return pl.DataFrame(schema={
                "event_id": pl.Int64,
                "outcome_name": pl.Utf8,
                "horizon": pl.Int64,
                "value": pl.Float64,
                "diagnostics": pl.Object,
            })

        result = pl.DataFrame(rows)
        BaseOutcome.check_outcome_table(result)
        return result

    def validate_params(self, params: dict) -> list[str]:
        errs = []
        horizons = params.get("horizons", [1, 5, 20])
        if not isinstance(horizons, list) or not horizons:
            errs.append("horizons must be a non-empty list")
        elif not all(isinstance(h, int) and h > 0 for h in horizons):
            errs.append("all horizons must be positive integers")
        return errs