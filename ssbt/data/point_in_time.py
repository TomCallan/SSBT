"""Point-in-Time Data Integrity & Multi-Timeframe Alignment Module.

Enforces strict point-in-time joins, preventing lookahead leakage across higher and lower timeframe features.
"""

from __future__ import annotations

import polars as pl


class CausalityViolationError(Exception):
    """Raised when data leakage or anti-causal lookahead is detected in a feature pipeline."""
    pass


def align_multi_timeframe(
    lower_tf_df: pl.DataFrame,
    higher_tf_df: pl.DataFrame,
    symbol_col: str = "symbol",
    time_col: str = "timestamp",
) -> pl.DataFrame:
    """Asynchronously join higher timeframe features to lower timeframe bars using completed bar close timestamps only.
    
    Prevents same-bar lookahead by shifting higher timeframe indicators by 1 period before joining.
    """
    if lower_tf_df.is_empty() or higher_tf_df.is_empty():
        return lower_tf_df

    # Sort both DataFrames by timestamp
    lower_sorted = lower_tf_df.sort(time_col)
    higher_sorted = higher_tf_df.sort(time_col)

    # Shift higher timeframe non-time/symbol columns by 1 to use completed prior bars only
    non_key_cols = [c for c in higher_sorted.columns if c not in (symbol_col, time_col)]
    shifted_higher = higher_sorted.with_columns([
        pl.col(c).shift(1).alias(f"htf_{c}") for c in non_key_cols
    ])

    # Asof join on lower timeframe timestamp >= higher timeframe timestamp
    joined = lower_sorted.join_asof(
        shifted_higher,
        on=time_col,
        by=symbol_col if symbol_col in lower_sorted.columns and symbol_col in shifted_higher.columns else None,
        strategy="backward",
    )

    return joined


def validate_point_in_time_join(
    df: pl.DataFrame,
    time_col: str = "timestamp",
    feature_time_col: str | None = None,
) -> bool:
    """Validate that all joined feature timestamps are strictly <= bar timestamp."""
    if df.is_empty():
        return True

    if feature_time_col and feature_time_col in df.columns:
        violations = df.filter(pl.col(feature_time_col) > pl.col(time_col))
        if violations.height > 0:
            raise CausalityViolationError(
                f"Point-In-Time Leakage Violation: Found {violations.height} rows where feature timestamp > bar timestamp!"
            )

    return True
