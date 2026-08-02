# Multi-Timeframe Signal Alignment

---
summary: Aligning multi-frequency bar streams (e.g. 1-minute execution bars with 1-hour macro signals) with point-in-time causality protection.
keywords: multi timeframe, signal alignment, point in time, asof join, causality, zero lookahead
domain: data-engineering
difficulty: intermediate
primary_apis: ssbt.data.align_multi_timeframe, ssbt.data.validate_point_in_time_join
related_pages: /docs/use-cases/index.md, /docs/reference/feeds.md, /docs/trust-and-validation/index.md
---

## 1. Objective
Merge high-frequency execution bars (e.g., 1-minute) with lower-frequency signal indicators (e.g., 1-hour moving averages) using point-in-time `asof` alignment to strictly prevent lookahead bias and future bar timestamp leakage.

## 2. Inputs
- `df_fast`: 1-minute Polars DataFrame with schema `[timestamp, open, high, low, close, volume]`
- `df_slow`: 1-hour Polars DataFrame with computed indicator `[timestamp, macro_trend]`

## 3. Minimal Code

```python
import polars as pl
from ssbt.data import align_multi_timeframe, validate_point_in_time_join

# Generate synthetic fast (1m) and slow (1h) data
timestamps_fast = pl.date_range(pl.datetime(2026, 1, 1), pl.datetime(2026, 1, 2), "1m", eager=True)
df_fast = pl.DataFrame({"timestamp": timestamps_fast, "close": 100.0})

timestamps_slow = pl.date_range(pl.datetime(2026, 1, 1), pl.datetime(2026, 1, 2), "1h", eager=True)
df_slow = pl.DataFrame({"timestamp": timestamps_slow, "macro_signal": [1 if i % 2 == 0 else -1 for i in range(len(timestamps_slow))]})

# Align multi-timeframe streams point-in-time
aligned_df = align_multi_timeframe(
    high_freq_df=df_fast,
    low_freq_df=df_slow,
    on="timestamp",
    suffix="_slow"
)

# Validate point-in-time join integrity
validate_point_in_time_join(aligned_df, fast_time_col="timestamp", slow_time_col="timestamp_slow")
print(aligned_df.head(10))
```

## 4. Realistic Settings
- **Join Strategy**: Backward `join_asof` matching the latest completed hourly bar.
- **Lag Guard**: Enforce explicit 1-bar publication lag on `df_slow` to account for reporting latency.

## 5. Expected Artifacts
```
artifacts/multi_timeframe_run/
├── aligned_bars.parquet
└── pit_join_validation_report.json
```

## 6. Failure Modes
- **Forward Looking Leakage**: Using `strategy="nearest"` or `strategy="forward"` which pulls future prices.
- **Unsorted Timestamps**: `join_asof` requires strictly ascending sorted timestamps; non-monotonic timestamps raise `ValueError`.

## 7. Validation Checks
```python
# Verify fast timestamp is strictly greater than or equal to slow timestamp
time_diffs = aligned_df["timestamp"] - aligned_df["timestamp_slow"]
assert (time_diffs.dt.total_milliseconds() >= 0).all(), "Causality violated: slow timestamp in future!"
```

## 8. Production Checklist
- [ ] Confirm both DataFrames have sorted `timestamp` columns.
- [ ] Run `validate_point_in_time_join()` before passing data into `InMemoryFeed`.
- [ ] Log snapshot hash in `simulation_assumptions_report.json`.
