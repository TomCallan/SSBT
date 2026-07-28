# SSBT — High-Performance Quantitative Exploration & Backtesting Engine

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Performance](https://img.shields.io/badge/engine-Polars%20%7C%20Numba%20%7C%20Zero--Allocation-green.svg)]()
[![Audit Status](https://img.shields.io/badge/audit-Anti--Lookahead%20Verified-brightgreen.svg)]()

SSBT is an ultra-fast, event-driven quantitative backtesting and research engine engineered for traders, quantitative researchers, and automated strategy developers. Built on top of Polars, NumPy, and Numba, SSBT eliminates Python loop overhead while maintaining 100% causal execution integrity and strict anti-lookahead auditing.

---

## Key Quant Engine Capabilities

- Zero-Allocation Bar Execution Loop: Pre-allocated memory structures eliminate per-bar object creation, delivering execution speeds over 1,000,000 bars/sec.
- Anti-Lookahead Causal Audit System (AuditLogger): Built-in lineage tracing verifies that every order, fill, and metric calculation strictly respects temporal causality. Outputs SHA-256 integrity signatures for strategy validation.
- Prop Challenge Compliance Engine: Evaluates systematic strategies against institutional prop firm rules (e.g. Velotrade $5k account rules: Max Daily Loss -$250, Max Total Loss -$500, +8% Target Equity).
- Multi-Ticker & Multi-Timeframe Matrix Framework: Evaluates performance matrices across asset classes (Gold, Silver, Crude Oil, Crypto, Tech Stocks) and timeframes (1d, 1h, 15m).
- Real-Time Execution Stream (ExecutionStreamPublisher): Publishes JSON-lines events (BAR, ORDER, FILL, TRADE, EQUITY) over IPC / sockets for live GUI dashboards (Tkinter & Web browsers).
- Standardized Visual Reporting Suite: Automated generation of performance heatmaps (test_matrix_plot.png) and multi-asset equity growth curves (multi_equity_curves.png).

---

## System Architecture & Mechanics

```
  +-------------------------------------------------------------+
  |                   External Market Data                      |
  |          (yfinance, Parquet, CCXT, CSV, Polars)             |
  +------------------------------+------------------------------+
                                 |
                                 v
  +-------------------------------------------------------------+
  |                 ssbt.data.feed.InMemoryFeed                 |
  |           (Contiguous Arrow / Numba Column Arrays)          |
  +------------------------------+------------------------------+
                                 |
                                 v
  +-------------------------------------------------------------+
  |                 ssbt.core.engine.Engine                     |
  |       +----------------------------------------------+      |
  |       | Single-Symbol & Multi-Symbol Fast Matching  |      |
  |       +----------------------+-----------------------+      |
  |                              |                              |
  |   +--------------------------+--------------------------+   |
  |   |                                                     |   |
  |   v                                                     v   |
  | +------------------------+             +--------------+ |   |
  | | ssbt.strategy.Strategy |             |  Portfolio   | |   |
  | +------------------------+             +--------------+ |   |
  +------------------------------+------------------------------+
                                 |
             +-------------------+-------------------+
             v                                       v
  +----------------------+               +----------------------+
  |   ssbt.analytics     |               |  ExecutionStream     |
  |    .AuditLogger      |               |     Publisher        |
  | (Anti-Lookahead Causal|               |(Real-Time JSONL IPC  |
  |      Audit Trail)    |               |    for GUIs / Web)   |
  +----------------------+               +----------------------+
```

---

## Structural Examples & Usage Guides

### 1. Writing a Quant Strategy (Strategy API)

Strategies inherit from ssbt.Strategy and implement on_bar(). Use self.is_flat(engine, symbol) to verify position status before entry:

```python
import numpy as np
import polars as pl
from ssbt import Strategy, Side, Order, OrderType, OrderStatus, Bar

class TripleConfluenceStrategy(Strategy):
    """EMA Trend + RSI Momentum + Dynamic ATR Trailing Stop Loss."""

    def __init__(self, risk_dollars: float = 85.0):
        super().__init__()
        self.risk_dollars = risk_dollars
        self.closes = []
        self.highs = []
        self.lows = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)

        if len(self.closes) < 22:
            return

        # 1. EMA Trend Filter
        ema = float(np.mean(self.closes[-20:]))

        # 2. RSI Momentum Filter
        diffs = np.diff(self.closes[-15:])
        gains = np.where(diffs > 0, diffs, 0.0)
        losses = np.where(diffs < 0, -diffs, 0.0)
        rs = np.mean(gains) / (np.mean(losses) + 1e-8)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # 3. ATR Volatility Trailing Stop
        tr = np.maximum(
            np.array(self.highs[-10:]) - np.array(self.lows[-10:]),
            np.abs(np.array(self.highs[-10:]) - np.array(self.closes[-11:-1]))
        )
        atr = float(np.mean(tr))

        # Entry logic: Only enter when FLAT
        if bar.close > ema and 45.0 <= rsi <= 65.0 and self.is_flat(engine, bar.symbol):
            stop_dist = max(1.8 * atr, bar.close * 0.008)
            qty = round(self.risk_dollars / stop_dist, 2)

            # Submit Market Buy and Trailing Stop Loss
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty))
            engine.submit_order(Order(
                id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
            ))
```

---

### 2. Running a Multi-Ticker & Multi-Timeframe Strategy Matrix

Execute backtests across tickers (GC=F, SI=F, CL=F, BTC-USD) and timeframes (1d, 1h), automatically generating matrix heatmaps:

```python
import polars as pl
import yfinance as yf
from ssbt import BacktestAdapter, InMemoryFeed, generate_matrix_heatmap_chart, generate_multi_equity_curve_chart

# 1. Fetch Market Data & Convert to Polars InMemoryFeed
df_pd = yf.download("GC=F", period="1y", interval="1d")
pl_df = pl.DataFrame({
    "timestamp": df_pd.index.astype("int64").values,
    "symbol": ["GC=F"] * len(df_pd),
    "open": df_pd["Open"].values.astype(float),
    "high": df_pd["High"].values.astype(float),
    "low": df_pd["Low"].values.astype(float),
    "close": df_pd["Close"].values.astype(float),
    "volume": df_pd["Volume"].values.astype(float),
})

feed = InMemoryFeed(pl_df, symbol="GC=F")
adapter = BacktestAdapter(initial_cash=5000.0)

# 2. Run Engine & Extract Standardized Metrics
res = adapter.run_backtest(feed, TripleConfluenceStrategy())
print(f"Final Equity: ${res['final_equity']:,.2f} | Sharpe: {res['metrics']['sharpe']:.2f}")
```

---

### 3. Launching Real-Time GUIs (Desktop & Web)

SSBT includes interactive GUIs in gui_examples/:

#### Interactive Tkinter Desktop GUI:
```bash
uv run python gui_examples/desktop_gui.py
```

#### Interactive Web Dashboard (Browser):
```bash
uv run python gui_examples/web_gui.py
```
Open http://localhost:8080 in any web browser to launch strategies live and view real-time HTML5 Canvas equity curves.

---

### 4. Running the Causal Anti-Lookahead Audit

Verify execution integrity and generate SHA-256 audit reports:

```python
from ssbt import AuditLogger

logger = AuditLogger(verbose=True)
report = logger.generate_report(backtest_result=res['raw_result'], output_dir="artifacts/run_01")
print(f"Audit Passed: {report.passed} | SHA-256: {report.sha256_hash}")
```

---

## Testing & Verification

Run the full pytest suite (133 unit and integration tests):

```bash
uv run python -m pytest ssbt/tests/ -v
```

Run the Prop Challenge Optimization Suite:

```bash
uv run python examples/multi_ticker_timeframe_suite.py
```

---

## Repository Layout

```
SSBT/
├── ssbt/                         # Core SSBT Quantitative Package
│   ├── core/                     # Engine, Portfolio, Matching, Events
│   ├── data/                     # InMemory & Parquet Data Feeds
│   ├── strategy/                 # Strategy Base Class & Position Helpers
│   ├── analytics/                # AuditLogger, Metrics, Stream Publisher, Terminal
│   └── experiments/              # Exploration Engine, Spec Parser & Charting
├── gui_examples/                 # Real-time Interactive GUIs
│   ├── desktop_gui.py            # Tkinter Desktop Quantitative Studio
│   └── web_gui.py                # Web Browser Dashboard & HTTP API Server
├── strategies_vault/             # Proprietary Strategy Vault (Gitignored)
│   └── triple_confluence.py      # Production Triple Confluence Strategy
├── examples/                     # Ready-to-Run Research & Matrix Suites
│   ├── multi_ticker_timeframe_suite.py
│   ├── velotrade_5k_challenge.py
│   └── triple_confluence_detail.py
├── artifacts/                    # Run Artifacts, Charts & Audit Trails (Gitignored)
├── pyproject.toml                # Package configuration (Python 3.12+)
└── README.md                     # Engine Documentation & Guides
```

---

## License
MIT License. Engineered for quantitative trading, systematic strategy exploration, and prop challenge evaluation.
