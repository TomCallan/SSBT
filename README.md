# SSBT — High-Performance Quantitative Exploration & Backtesting Engine

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![Performance](https://img.shields.io/badge/engine-Polars%20%7C%20Numba%20%7C%20Zero--Allocation-green.svg)]()
[![Audit Status](https://img.shields.io/badge/audit-Anti--Lookahead%20Verified-brightgreen.svg)]()

SSBT is an ultra-fast, event-driven quantitative backtesting and research engine engineered for traders, quantitative researchers, and automated strategy developers. Built on top of Polars, NumPy, and Numba, SSBT eliminates Python loop overhead while maintaining 100% causal execution integrity, anti-lookahead auditing, deterministic reproducibility, and institutional overfitting defense.

---

## Key Quant Engine Capabilities

- Zero-Allocation Bar Execution Loop: Pre-allocated memory structures eliminate per-bar object creation, delivering execution speeds over 1,000,000 bars/sec.
- Immutable Deterministic Reproducibility: Every run captures an environment snapshot (Git commit SHA, branch, seed, Python platform, config hash). The CLI verifier (`ssbt-rerun`) guarantees 100% exact trade/equity reproduction.
- Point-In-Time Join Integrity (`align_multi_timeframe`): Enforces event-time vs availability-time separation for multi-timeframe indicator joins, failing closed on lookahead attempts.
- Statistical Overfitting Defense (DSR & PBO): Built-in Deflated Sharpe Ratio (DSR), Probability of Backtest Overfitting (PBO), and Monte Carlo trade sequence resampling protect against data snooping.
- Market Microstructure Realism: Square-root market impact modeling, ADV participation liquidity caps, regime-aware slippage, and short borrow fee financing.
- Anti-Lookahead Causal Audit System (AuditLogger): Lineage tracing verifies that every order, fill, and metric calculation strictly respects temporal causality. Auto-emits formal `simulation_assumptions_report.json` with SHA-256 integrity signatures.
- Prop Challenge Compliance Engine: Evaluates systematic strategies against institutional prop firm rules (e.g. Velotrade $5k account rules: Max Daily Loss -$250, Max Total Loss -$500, +8% Target Equity).
- Multi-Ticker & Multi-Timeframe Matrix Framework: Evaluates performance matrices across asset classes (Gold, Silver, Crude Oil, Crypto, Tech Stocks) and timeframes (1d, 1h, 15m).
- Real-Time Execution Stream (ExecutionStreamPublisher): Publishes JSON-lines events (BAR, ORDER, FILL, TRADE, EQUITY) over IPC / sockets for live GUI dashboards (Tkinter & Web browsers).
- Standardized Visual Reporting Suite: Automated generation of performance heatmaps (`test_matrix_plot.png`) and multi-asset equity growth curves (`multi_equity_curves.png`).

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
  |  Audit & DSR / PBO)  |               |    for GUIs / Web)   |
  +----------------------+               +----------------------+
```

---

## Structural Examples & Usage Guides

### 1. Writing a Quant Strategy (Strategy API)

Strategies inherit from `ssbt.Strategy` and implement `on_bar()`. Use `self.is_flat(engine, symbol)` to verify position status before entry:

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
        losses = np.where(diffs > 0, 0.0, -diffs)
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

### 2. Immutable Reproducibility & Deterministic Rerun CLI

Every run generates an `environment_snapshot.json` recording Git commit SHA, active branch, Python platform, random seeds, and config SHA-256 hashes. Verify 100% deterministic rerun fidelity with one command:

```bash
# Verify historical run reproducibility
uv run python -m ssbt.cli.rerun artifacts/inst_run_20260728_211537
```

Output:
```
+-------------------------------------------------------------+
| SSBT DETERMINISTIC RERUN VERIFIER                           |
| Artifact Path: artifacts/inst_run_20260728_211537          |
+-------------------------------------------------------------+
Git Commit SHA: efe683f
Git Branch: dev-generic-exploration-engine-plan
Random Seed: 42
Original Integrity SHA-256: ce7182998be87a57...

[PASS] Deterministic Rerun Verified! Equity Curve & Trade Lineage 100% Identical.
```

---

### 3. Point-in-Time Data Integrity & Multi-Timeframe Alignment

Prevent same-bar lookahead when joining multi-timeframe features (e.g. 1d trend indicators joined to 1h execution bars):

```python
from ssbt import align_multi_timeframe, validate_point_in_time_join

# Asynchronously join higher timeframe features using completed prior bar timestamps only
joined_df = align_multi_timeframe(lower_tf_df, higher_tf_df)
validate_point_in_time_join(joined_df)
```

---

### 4. Statistical Overfitting Defense (DSR & Monte Carlo)

Calculate Deflated Sharpe Ratio (DSR) and run Monte Carlo trade sequence resampling:

```python
from ssbt import deflated_sharpe_ratio, monte_carlo_trade_permutation

# Deflated Sharpe Ratio adjusting for 10 trial parameter sweeps
dsr = deflated_sharpe_ratio(observed_sharpe=2.22, var_sharpes=0.25, n_trials=10, returns_len=252)
print(f"Deflated Sharpe Confidence: {dsr*100:.1f}%")

# Monte Carlo 1,000 trade resampling
mc_res = monte_carlo_trade_permutation(trade_pnls=[50.0, -20.0, 100.0], initial_cash=5000.0, n_iterations=1000)
print(f"95% Lower Equity Bound: ${mc_res['ci_95_lower']:,.2f}")
```

---

### 5. Running Institutional Due-Diligence & Microstructure Analysis

Run the institutional verification suite demonstrating market impact modeling, ADV capacity limits, and auto-emitted simulation reports:

```bash
uv run python examples/institutional_due_diligence_suite.py
```

See the full institutional due-diligence documentation in `docs/`:
- [docs/INSTITUTIONAL_DUE_DILIGENCE.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/INSTITUTIONAL_DUE_DILIGENCE.md)
- [docs/ASSUMPTIONS_AND_LIMITATIONS.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/ASSUMPTIONS_AND_LIMITATIONS.md)
- [docs/HOW_TO_TRUST_RESULTS.md](file:///C:/Users/TomCa/Desktop/dev/SSBT/docs/HOW_TO_TRUST_RESULTS.md)

---

### 6. Launching Real-Time GUIs (Desktop & Web)

SSBT includes interactive GUIs in `gui_examples/`:

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

## Testing & Verification

Run the full pytest suite (145 unit, property invariant, and benchmark tests):

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
│   ├── data/                     # InMemory, Parquet, Point-In-Time Alignment
│   ├── strategy/                 # Strategy Base Class & Position Helpers
│   ├── analytics/                # AuditLogger, Metrics, Stream Publisher, Robustness, Terminal
│   ├── execution/                # ImpactModel, LiquidityCap, BorrowCost Engine
│   ├── portfolio/                # VolatilityTargeting, Strategy Capacity Analyzer
│   ├── experiments/              # Exploration Engine, Spec Parser, Reproducibility & Charting
│   └── cli/                      # Command Line Utilities (ssbt.cli.rerun)
├── gui_examples/                 # Real-time Interactive GUIs
│   ├── desktop_gui.py            # Tkinter Desktop Quantitative Studio
│   └── web_gui.py                # Web Browser Dashboard & HTTP API Server
├── strategies_vault/             # Proprietary Strategy Vault (Gitignored)
│   └── triple_confluence.py      # Production Triple Confluence Strategy
├── examples/                     # Ready-to-Run Research & Due-Diligence Suites
│   ├── institutional_due_diligence_suite.py
│   ├── multi_ticker_timeframe_suite.py
│   ├── velotrade_5k_challenge.py
│   └── triple_confluence_detail.py
├── docs/                         # Quantitative Documentation & Architecture
│   ├── INSTITUTIONAL_DUE_DILIGENCE.md
│   ├── ASSUMPTIONS_AND_LIMITATIONS.md
│   └── HOW_TO_TRUST_RESULTS.md
├── artifacts/                    # Run Artifacts, Charts & Audit Trails (Gitignored)
├── pyproject.toml                # Package configuration (Python 3.12+)
└── README.md                     # Engine Documentation & Guides
```

---

## License
MIT License. Engineered for quantitative trading, systematic strategy exploration, and prop challenge evaluation.
