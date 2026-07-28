# SSBT — Super Speedy Backtesting Tool & Generic Exploration Engine

**SSBT** is a high-speed Python research platform and event-driven backtesting engine. It bridges the gap between fast vectorised backtesters (which lack market realism) and event-driven backtesters (which are slow).

With SSBT, you get **300k+ bars/sec** in event-driven mode and **3.5M+ bars/sec** in vectorised mode — complete with realistic order types (Market, Limit, Stop, Stop-Limit, Trailing Stop, OCO, and TimeInForce execution).

---

## Key Pillars

1. **Generic Event Exploration Engine**: Evaluate market hypotheses, signal triggers, and multi-horizon forward returns (1b, 5b, 10b, 20b, 50b) without running full strategy simulations.
2. **Bootstrap Statistical Confidence**: Perform 1,000–2,000 iteration non-parametric resampling to compute 95% confidence intervals on return distributions.
3. **High-Speed Numba Order Engine**: C-speed order matching compiled via Numba `@njit` kernels, avoiding Python GIL and per-tick object allocations.
4. **Decoupled Data Architecture**: External data ingestion via Polars zero-copy Apache Arrow memory buffers (compatible with `yfinance`, CCXT, Parquet, and SQL).
5. **Execution Lineage & Auditability**: Anti-lookahead timestamp verification, causal fill checking, and `audit_trail.json` SHA-256 manifest generation.
6. **Rich Terminal Displays & Reporting**: Render rich terminal tables, statistics, and audit banners directly in the terminal using `rich`.

---

## Quickstart

### 1. Installation

```bash
# Clone and install with uv
git clone https://github.com/TomCallan/SSBT.git
cd SSBT
uv sync
```

### 2. Run an Event Study Experiment via CLI

Create a YAML experiment spec (`experiment.yaml`):

```yaml
version: 1
experiment:
  name: "volume_spike_study"
  type: event_study

dataset:
  source: "data/sp500.parquet"
  symbol: "SPY"
  timeframe: "1d"

events:
  - name: "volume_spike"
    params: { window: 20, multiplier: 2.5 }

outcomes:
  - name: "forward_return"
    params: { horizons: [1, 5, 20, 50] }

analysis:
  confidence: { method: "bootstrap", iterations: 1000, ci: 0.95 }

reporting:
  output_dir: "artifacts"
  formats: ["csv", "json", "parquet"]
  charts: ["distribution", "grouped_bar", "event_timeline"]
```

Execute from CLI:
```bash
ssbt-run experiment.yaml
```

---

## Code Examples

### 1. High-Speed Strategy Backtesting with Trailing Stops

```python
import polars as pl
import yfinance as yf
from ssbt.strategy.base import Strategy
from ssbt.core.events import Side, OrderType, Order, OrderStatus
from ssbt.data.feed import InMemoryFeed
from ssbt.backtest.adapter import BacktestAdapter

# 1. Fetch data externally (SSBT is decoupled from data sources)
df_pd = yf.download("GC=F", period="1y", interval="1d", progress=False).reset_index()
df = pl.DataFrame({
    "timestamp": (df_pd["Date"].astype("int64")).values,
    "symbol": ["GC=F"] * len(df_pd),
    "open": df_pd["Open"].values.astype(float),
    "high": df_pd["High"].values.astype(float),
    "low": df_pd["Low"].values.astype(float),
    "close": df_pd["Close"].values.astype(float),
    "volume": df_pd["Volume"].values.astype(float),
})

# 2. Define Strategy with Trailing Stop Loss
class VolumeBreakoutStrategy(Strategy):
    def on_bar(self, bar, engine):
        if bar.volume > 2.5 * 1000.0:  # Spike condition
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, 10.0))
            engine.submit_order(Order(
                id=0, symbol=bar.symbol, side=Side.SELL,
                type=OrderType.TRAILING_STOP, qty=10.0,
                trail_offset=bar.close * 0.03, status=OrderStatus.PENDING
            ))

# 3. Run Backtest
adapter = BacktestAdapter(initial_cash=100_000.0)
result = adapter.run_backtest(InMemoryFeed(df, symbol="GC=F"), VolumeBreakoutStrategy())

print("Sharpe Ratio:", result["metrics"]["sharpe"])
print("Final Equity: $", result["final_equity"])
```

### 2. Audit Trail & Rich Terminal Outputs

```python
from ssbt.analytics.audit import AuditLogger
from ssbt.analytics.terminal import display_audit_status, display_backtest_summary

logger = AuditLogger(verbose=False)
report = logger.generate_report(backtest_result=result["raw_result"], output_dir="artifacts")

display_audit_status(report)
display_backtest_summary(result["metrics"], result["trades"])
```

---

## Documentation Map

* **Master Guide & Commodity Study**: [example.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/example.md)
* **Architecture Deep-Dive**: [docs/COMMODITY_RESEARCH_EXPLAINED.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/COMMODITY_RESEARCH_EXPLAINED.md)
* **LLM Agent Reference**: [llms.txt](file:///C:/Users/TomCa/Desktop/dev/SSBT/llms.txt)
* **Claude / OpenCode Skill**: [.claude/skills/ssbt-exploration/SKILL.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/.claude/skills/ssbt-exploration/SKILL.md)

---

## License

MIT License.
