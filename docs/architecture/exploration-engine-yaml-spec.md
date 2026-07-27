# Exploration Engine YAML Specification (SSBT)

## 1) Design Objectives
- Human-readable hypothesis declaration
- Strong validation with actionable errors
- Deterministic defaults
- Easy composition (filters, groups, multiple outcomes)

---

## 2) Top-Level Schema

```yaml
version: 1
experiment:
  name: string
  type: event_study | backtest
  description: string

dataset:
  source: string
  symbol: string | [string]
  timeframe: string
  start: "YYYY-MM-DD"
  end: "YYYY-MM-DD"
  timezone: "UTC"
  adjustments:
    split_adjusted: bool
    dividend_adjusted: bool

features:
  - name: string
    kind: indicator | transform | custom
    params: {}

events:
  - name: string
    params: {}
    cooldown_bars: int
    min_separation_bars: int

outcomes:
  - name: string
    params: {}

filters:
  pre_event: []
  post_event: []

group_by:
  - string

analysis:
  confidence:
    method: bootstrap | none
    iterations: int
    ci: float
  statistics:
    include: [mean, median, std, hit_rate, quantiles]
    quantiles: [0.05, 0.25, 0.5, 0.75, 0.95]

reporting:
  output_dir: string
  formats: [csv, json, parquet]
  charts: [distribution, grouped_bar, event_timeline]

execution:
  seed: int
  max_workers: int
  cache_features: bool
  fail_on_warnings: bool
```

---

## 3) Required vs Optional

Required:
- `version`
- `experiment.name`
- `experiment.type`
- `dataset.source`
- `events`
- `outcomes`

Optional with defaults:
- `dataset.timezone` default `UTC`
- `analysis.confidence.method` default `none`
- `execution.seed` default deterministic engine seed
- `reporting.formats` default `[csv, json]`

---

## 4) Validation Rules

1. `version` must match supported schema versions.
2. `events[].name` must resolve in event registry.
3. `outcomes[].name` must resolve in outcome registry.
4. All referenced feature names must exist or be derivable.
5. `dataset.start < dataset.end`.
6. `analysis.confidence.ci` in `(0, 1)`.
7. `quantiles` strictly increasing and in `[0, 1]`.
8. No duplicate `events[].name` aliases in same config unless uniquely keyed.
9. Multi-asset mode requires symbol-aware grouping or explicit aggregation mode.

---

## 5) Example: Volume Spike vs Forward Return

```yaml
version: 1
experiment:
  name: volume_spike_vs_price_move
  type: event_study
  description: "Evaluate forward return behavior after large relative volume spikes"

dataset:
  source: data/BTCUSDT_1m.parquet
  symbol: BTCUSDT
  timeframe: 1m
  start: "2024-01-01"
  end: "2024-12-31"
  timezone: UTC

features:
  - name: vol_sma_50
    kind: indicator
    params:
      indicator: sma
      field: volume
      window: 50
  - name: atr_14_pct
    kind: indicator
    params:
      indicator: atr_pct
      window: 14

events:
  - name: volume_spike
    params:
      volume_field: volume
      baseline_feature: vol_sma_50
      multiplier: 3.0
    cooldown_bars: 3
    min_separation_bars: 1

outcomes:
  - name: forward_return
    params:
      field: close
      horizons: [1, 5, 20]
  - name: max_excursion
    params:
      field: close
      horizon: 20

filters:
  pre_event:
    - "atr_14_pct > 0.5"
  post_event: []

group_by:
  - market_regime
  - hour

analysis:
  confidence:
    method: bootstrap
    iterations: 2000
    ci: 0.95
  statistics:
    include: [mean, median, std, hit_rate, quantiles]
    quantiles: [0.05, 0.25, 0.5, 0.75, 0.95]

reporting:
  output_dir: artifacts/volume_spike_vs_price_move
  formats: [csv, json, parquet]
  charts: [distribution, grouped_bar, event_timeline]

execution:
  seed: 42
  max_workers: 4
  cache_features: true
  fail_on_warnings: false
```

---

## 6) Error Messaging Standard

Validation errors should include:
- JSONPath-like field path
- expected vs actual
- suggested fix

Example:
- `events[0].params.multiplier: expected > 0, received -1.0. Suggestion: use a positive threshold like 2.0 or 3.0.`

---

## 7) Versioning Strategy

- `version` is mandatory.
- Add migration helpers for `v1 -> v2` when schema evolves.
- Keep parser backward compatibility for at least one major spec version.
