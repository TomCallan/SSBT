"""Portfolio allocation functions for multi-symbol backtesting."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from ssbt.core.events import Bar

AllocationFn = Callable[[dict[str, Bar], int], dict[str, float]]


def equal_weight(bars: dict[str, Bar], timestamp: int) -> dict[str, float]:
    """Equal weight across all symbols."""
    n = len(bars)
    return {s: 1.0 / n for s in bars} if n else {}


def inverse_volatility(prices: dict[str, list[float]], lookback: int = 20) -> AllocationFn:
    """Factory: allocate by inverse volatility (equal risk contribution)."""
    vol_data: dict[str, np.ndarray] = {}
    for sym, price_list in prices.items():
        arr = np.array(price_list, dtype=np.float64)
        returns = np.diff(arr) / arr[:-1]
        rolling_vol = np.empty(len(arr), dtype=np.float64)
        rolling_vol[:lookback] = 0.0
        for i in range(lookback, len(arr)):
            rolling_vol[i] = np.std(returns[i - lookback:i], ddof=1)
        vol_data[sym] = rolling_vol

    def alloc_fn(bars, timestamp):
        inv_vols = {}
        for sym in bars:
            if sym in vol_data:
                v = vol_data[sym][-1]
                inv_vols[sym] = 1.0 / v if v > 0 else 0.0
            else:
                inv_vols[sym] = 0.0
        total = sum(inv_vols.values())
        if total > 0:
            return {s: v / total for s, v in inv_vols.items()}
        return equal_weight(bars, timestamp)
    return alloc_fn


def custom_allocation(fn: Callable[[dict[str, Bar], int, dict], dict[str, float]], **context) -> AllocationFn:
    """Wrap a custom allocation function with context dict.

    The custom fn receives (bars, timestamp, context_dict) and returns weights.
    """
    ctx = dict(context)
    return lambda bars, timestamp: fn(bars, timestamp, ctx)
