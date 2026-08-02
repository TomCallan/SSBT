# Data Feeds API Reference (`ssbt.data`)

---
summary: API reference for data ingestion feeds, tick processing, order book reconstruction, and point-in-time joins.
keywords: reference, feeds, InMemoryFeed, ParquetFeed, LiveStreamFeed, align_multi_timeframe, point in time
domain: api-reference
difficulty: intermediate
primary_apis: ssbt.InMemoryFeed, ssbt.ParquetFeed, ssbt.data.align_multi_timeframe, ssbt.data.validate_point_in_time_join
related_pages: /docs/index.md, /docs/reference/index.md, /docs/use-cases/multi-timeframe-signal-alignment.md
---

## `ssbt.InMemoryFeed`

Data feed wrapper consuming in-memory Polars DataFrames keyed by symbol.

```python
class InMemoryFeed(BaseFeed):
    def __init__(self, data: Dict[str, pl.DataFrame])
```

### Parameters
- `data`: Dictionary mapping symbol names (e.g. `"BTC-USD"`) to Polars DataFrames containing `[timestamp, open, high, low, close, volume]`.

---

## `ssbt.data.align_multi_timeframe`

Aligns multi-frequency DataFrames using backward `asof` joining to prevent lookahead bias.

```python
def align_multi_timeframe(
    high_freq_df: pl.DataFrame,
    low_freq_df: pl.DataFrame,
    on: str = "timestamp",
    suffix: str = "_slow"
) -> pl.DataFrame
```

### Return Contract
Returns joined Polars DataFrame where each high-frequency bar row contains the most recent completed low-frequency bar indicators without future leakage.

---

## `ssbt.data.rebuild_orderbook_from_bars`

Reconstructs synthetic L2 order book depth quotes from OHLCV bar data.

```python
def rebuild_orderbook_from_bars(
    df: pl.DataFrame,
    symbol: str,
    levels: int = 5,
    tick_size: float = 0.01
) -> OrderBookFeed
```
