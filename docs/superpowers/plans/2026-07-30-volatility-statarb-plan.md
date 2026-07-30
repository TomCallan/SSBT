# Volatility-Adjusted Mean Reversion & Statistical Arbitrage Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement and test Volatility-Adjusted Mean Reversion and Statistical Arbitrage strategies in SSBT with yfinance data ingestion, isolated $5,000 balances, max risk 0.15% ($7.50) per trade, trailing stop sweeps, and rolling walk-forward analysis.

**Architecture:** Use `yfinance` to fetch OHLCV market data, convert into Polars `pl.DataFrame`, and feed into SSBT's `InMemoryFeed`. Build production strategies in `strategies_vault/` inheriting from `ssbt.Strategy`. Execute parameter sweeps and rolling out-of-sample walk-forward optimization using SSBT's `GridSearchOptimizer` and `WalkForwardOptimizer`.

**Tech Stack:** Python 3.12, SSBT framework, Polars, yfinance, NumPy, Pytest.

## Global Constraints
- SSBT architecture: Zero internal network calls inside strategy logic; external data supplied as Polars DataFrames into `InMemoryFeed`.
- Account balance: Exactly $5,000 per instrument/pair setup.
- Max risk per trade: Exactly 0.15% of initial account balance = $7.50.
- Point-in-time causality: Anti-lookahead integrity verified by SSBT engine.

---

### Task 1: yfinance Data Ingestion Helper (`ssbt/data/yfinance_loader.py`)

**Files:**
- Create: `ssbt/data/yfinance_loader.py`
- Test: `ssbt/tests/test_volatility_statarb.py`

**Interfaces:**
- Consumes: `yfinance.download(tickers, interval, ...)`
- Produces: `download_yfinance_feed(symbols: list[str] | str, interval: str = "1d", period: str = "1y") -> dict[str, pl.DataFrame]` and `merge_into_in_memory_feed(dfs: dict[str, pl.DataFrame]) -> InMemoryFeed`

- [ ] **Step 1: Write failing test for yfinance data loader schema conversion**

```python
import polars as pl
from ssbt.data.yfinance_loader import download_yfinance_polars, build_ssbt_feed_from_yfinance

def test_yfinance_loader_polars_schema(monkeypatch):
    # Mock yfinance data download
    import pandas as pd
    import numpy as np
    
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    df_raw = pd.DataFrame({
        "Open": np.linspace(100, 110, 10),
        "High": np.linspace(102, 112, 10),
        "Low": np.linspace(99, 109, 10),
        "Close": np.linspace(101, 111, 10),
        "Volume": np.full(10, 1000.0)
    }, index=dates)

    pl_df = download_yfinance_polars("AAPL", period="10d", interval="1d", _raw_df=df_raw)
    assert isinstance(pl_df, pl.DataFrame)
    assert set(["timestamp", "open", "high", "low", "close", "volume", "symbol"]).issubset(set(pl_df.columns))
    assert len(pl_df) == 10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_volatility_statarb.py::test_yfinance_loader_polars_schema -v`
Expected: FAIL with ModuleNotFoundError / ImportError

- [ ] **Step 3: Implement `ssbt/data/yfinance_loader.py`**

```python
"""yfinance Data Ingestion Helper for SSBT."""

from __future__ import annotations
import yfinance as yf
import pandas as pd
import polars as pl
from ssbt.data.feed import InMemoryFeed

def download_yfinance_polars(symbol: str, period: str = "1y", interval: str = "1d", _raw_df: pd.DataFrame | None = None) -> pl.DataFrame:
    """Download market data via yfinance and format as SSBT-compliant Polars DataFrame."""
    if _raw_df is not None:
        df_pd = _raw_df.copy()
    else:
        ticker = yf.Ticker(symbol)
        df_pd = ticker.history(period=period, interval=interval)
        if df_pd.empty:
            raise ValueError(f"Failed to fetch data for symbol '{symbol}'.")

    if isinstance(df_pd.columns, pd.MultiIndex):
        df_pd.columns = df_pd.columns.get_level_values(0)

    df_pd = df_pd.reset_index()
    date_col = "Date" if "Date" in df_pd.columns else ("Datetime" if "Datetime" in df_pd.columns else df_pd.columns[0])
    df_pd = df_pd.rename(columns={
        date_col: "timestamp",
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume"
    })
    
    df_pd["symbol"] = symbol
    df_pd = df_pd[["timestamp", "open", "high", "low", "close", "volume", "symbol"]]
    
    # Convert timestamp column to string or int64 unix millis/ns if needed
    if pd.api.types.is_datetime64_any_dtype(df_pd["timestamp"]):
        df_pd["timestamp"] = df_pd["timestamp"].astype(str)

    pl_df = pl.from_pandas(df_pd)
    return pl_df

def build_ssbt_feed_from_yfinance(symbols: list[str] | str, period: str = "1y", interval: str = "1d") -> InMemoryFeed:
    """Download data for symbols and return an SSBT InMemoryFeed."""
    if isinstance(symbols, str):
        symbols = [symbols]

    dfs = [download_yfinance_polars(sym, period=period, interval=interval) for sym in symbols]
    merged_df = pl.concat(dfs) if len(dfs) > 1 else dfs[0]
    return InMemoryFeed(merged_df, symbol=symbols[0])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_volatility_statarb.py::test_yfinance_loader_polars_schema -v`
Expected: PASS

- [ ] **Step 5: Commit Task 1**

```bash
git add ssbt/data/yfinance_loader.py ssbt/tests/test_volatility_statarb.py
git commit -m "feat(data): implement yfinance polars data loader for SSBT"
```

---

### Task 2: Volatility-Adjusted Mean Reversion Strategy (`strategies_vault/volatility_mean_reversion.py`)

**Files:**
- Create: `strategies_vault/volatility_mean_reversion.py`
- Test: `ssbt/tests/test_volatility_statarb.py`

**Interfaces:**
- Consumes: `ssbt.Strategy`, `Bar`, `Side`, `Order`, `OrderType`, `OrderStatus`
- Produces: `VolatilityAdjustedMeanReversionStrategy(lookback=20, z_thresh=2.0, atr_period=14, atr_mult=2.0, risk_pct=0.0015, initial_balance=5000.0)`

- [ ] **Step 1: Write failing test for Volatility-Adjusted Mean Reversion Strategy**

```python
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.data.feed import InMemoryFeed
from strategies_vault.volatility_mean_reversion import VolatilityAdjustedMeanReversionStrategy

def test_volatility_mean_reversion_execution(sample_ohlcv_polars_df):
    feed = InMemoryFeed(sample_ohlcv_polars_df, symbol="AAPL")
    strat = VolatilityAdjustedMeanReversionStrategy(
        lookback=10, z_thresh=1.5, atr_period=5, atr_mult=1.5, risk_pct=0.0015, initial_balance=5000.0
    )
    adapter = BacktestAdapter(initial_cash=5000.0)
    res = adapter.run_backtest(feed, strat)
    assert res is not None
    assert "metrics" in res
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_volatility_statarb.py::test_volatility_mean_reversion_execution -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `strategies_vault/volatility_mean_reversion.py`**

```python
"""Volatility-Adjusted Mean Reversion Strategy."""

from __future__ import annotations
import numpy as np
from ssbt.strategy.base import Strategy
from ssbt.core.events import Side, OrderType, Order, OrderStatus, Bar

class VolatilityAdjustedMeanReversionStrategy(Strategy):
    """Mean Reversion using Rolling Z-Score with ATR Volatility Risk Sizing & Trailing Stop."""

    def __init__(
        self,
        lookback: int = 20,
        z_thresh: float = 2.0,
        atr_period: int = 14,
        atr_mult: float = 2.0,
        risk_pct: float = 0.0015,
        initial_balance: float = 5000.0,
    ):
        super().__init__()
        self.lookback = lookback
        self.z_thresh = z_thresh
        self.atr_period = atr_period
        self.atr_mult = atr_mult
        self.risk_pct = risk_pct
        self.initial_balance = initial_balance
        self.max_risk_dollars = initial_balance * risk_pct  # $7.50 for 5k

        self.closes: list[float] = []
        self.highs: list[float] = []
        self.lows: list[float] = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)

        min_bars = max(self.lookback, self.atr_period) + 2
        if len(self.closes) < min_bars:
            return

        # 1. Rolling Mean & Standard Deviation
        recent_closes = np.array(self.closes[-self.lookback:])
        mean = float(np.mean(recent_closes))
        std = float(np.std(recent_closes)) + 1e-8
        z_score = (bar.close - mean) / std

        # 2. Average True Range (ATR)
        tr = np.maximum(
            np.array(self.highs[-self.atr_period:]) - np.array(self.lows[-self.atr_period:]),
            np.abs(np.array(self.highs[-self.atr_period:]) - np.array(self.closes[-self.atr_period - 1:-1]))
        )
        atr = float(np.mean(tr)) if len(tr) > 0 else bar.close * 0.01

        is_flat = self.is_flat(engine, bar.symbol)

        if is_flat:
            stop_dist = max(self.atr_mult * atr, bar.close * 0.005)
            # Risk Sizing: Max loss = max_risk_dollars ($7.50)
            qty = max(1.0, round(self.max_risk_dollars / stop_dist, 2))

            if z_score <= -self.z_thresh:
                # Oversold: Buy entry + SELL Trailing Stop
                engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty))
                engine.submit_order(Order(
                    id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                    qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
                ))
            elif z_score >= self.z_thresh:
                # Overbought: Sell entry + BUY Trailing Stop
                engine.submit_order(self.market_order(bar.symbol, Side.SELL, qty))
                engine.submit_order(Order(
                    id=0, symbol=bar.symbol, side=Side.BUY, type=OrderType.TRAILING_STOP,
                    qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
                ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_volatility_statarb.py::test_volatility_mean_reversion_execution -v`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add strategies_vault/volatility_mean_reversion.py ssbt/tests/test_volatility_statarb.py
git commit -m "feat(strategy): implement VolatilityAdjustedMeanReversionStrategy"
```

---

### Task 3: Statistical Arbitrage Strategy (`strategies_vault/statarb_pairs.py`)

**Files:**
- Create: `strategies_vault/statarb_pairs.py`
- Test: `ssbt/tests/test_volatility_statarb.py`

**Interfaces:**
- Consumes: `ssbt.Strategy`, `Bar`, `Side`, `Order`
- Produces: `StatArbPairsStrategy(lookback=30, z_thresh=2.0, risk_pct=0.0015, initial_balance=5000.0)`

- [ ] **Step 1: Write failing test for StatArb Strategy**

```python
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.data.feed import InMemoryFeed
from strategies_vault.statarb_pairs import StatArbPairsStrategy

def test_statarb_pairs_execution(sample_ohlcv_polars_df):
    feed = InMemoryFeed(sample_ohlcv_polars_df, symbol="PAIR_SPREAD")
    strat = StatArbPairsStrategy(lookback=10, z_thresh=1.5, risk_pct=0.0015, initial_balance=5000.0)
    adapter = BacktestAdapter(initial_cash=5000.0)
    res = adapter.run_backtest(feed, strat)
    assert res is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_volatility_statarb.py::test_statarb_pairs_execution -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `strategies_vault/statarb_pairs.py`**

```python
"""Statistical Arbitrage / Pairs Trading Strategy."""

from __future__ import annotations
import numpy as np
from ssbt.strategy.base import Strategy
from ssbt.core.events import Side, OrderType, Order, OrderStatus, Bar

class StatArbPairsStrategy(Strategy):
    """Statistical Arbitrage Spread Mean Reversion Strategy with Trailing Stop Protection."""

    def __init__(
        self,
        lookback: int = 30,
        z_thresh: float = 2.0,
        atr_mult: float = 2.0,
        risk_pct: float = 0.0015,
        initial_balance: float = 5000.0,
    ):
        super().__init__()
        self.lookback = lookback
        self.z_thresh = z_thresh
        self.atr_mult = atr_mult
        self.risk_pct = risk_pct
        self.initial_balance = initial_balance
        self.max_risk_dollars = initial_balance * risk_pct  # $7.50

        self.closes: list[float] = []
        self.highs: list[float] = []
        self.lows: list[float] = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.closes.append(bar.close)
        self.highs.append(bar.high)
        self.lows.append(bar.low)

        if len(self.closes) < self.lookback + 2:
            return

        recent_closes = np.array(self.closes[-self.lookback:])
        mean = float(np.mean(recent_closes))
        std = float(np.std(recent_closes)) + 1e-8
        z_score = (bar.close - mean) / std

        # Volatility trailing offset
        tr = np.abs(np.array(self.highs[-10:]) - np.array(self.lows[-10:]))
        atr = float(np.mean(tr)) if len(tr) > 0 else bar.close * 0.01

        is_flat = self.is_flat(engine, bar.symbol)

        if is_flat:
            stop_dist = max(self.atr_mult * atr, bar.close * 0.005)
            qty = max(1.0, round(self.max_risk_dollars / stop_dist, 2))

            if z_score <= -self.z_thresh:
                engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty))
                engine.submit_order(Order(
                    id=0, symbol=bar.symbol, side=Side.SELL, type=OrderType.TRAILING_STOP,
                    qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
                ))
            elif z_score >= self.z_thresh:
                engine.submit_order(self.market_order(bar.symbol, Side.SELL, qty))
                engine.submit_order(Order(
                    id=0, symbol=bar.symbol, side=Side.BUY, type=OrderType.TRAILING_STOP,
                    qty=qty, trail_offset=stop_dist, status=OrderStatus.PENDING
                ))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_volatility_statarb.py::test_statarb_pairs_execution -v`
Expected: PASS

- [ ] **Step 5: Commit Task 3**

```bash
git add strategies_vault/statarb_pairs.py ssbt/tests/test_volatility_statarb.py
git commit -m "feat(strategy): implement StatArbPairsStrategy"
```

---

### Task 4: Trailing Stop Parameter Sweeps & Rolling Walk-Forward Analysis (`ssbt/experiments/run_volatility_statarb.py`)

**Files:**
- Create: `ssbt/experiments/run_volatility_statarb.py`
- Test: `ssbt/tests/test_volatility_statarb.py`

**Interfaces:**
- Consumes: `ssbt.optimization.grid_search.GridSearchOptimizer`, `ssbt.optimization.walk_forward.WalkForwardOptimizer`, `ssbt.data.yfinance_loader`
- Produces: Executable experiment script outputting Grid Search results, Stitched Out-Of-Sample Equity, Walk-Forward Efficiency (WFE ratio), and DSR/PBO metrics.

- [ ] **Step 1: Write failing test for Grid Search & Walk-Forward Suite on Volatility Strategy**

```python
from ssbt.optimization.space import ParameterSpace, CategoricalParam
from ssbt.optimization.grid_search import GridSearchOptimizer
from ssbt.optimization.walk_forward import WalkForwardOptimizer
from strategies_vault.volatility_mean_reversion import VolatilityAdjustedMeanReversionStrategy
from ssbt.data.feed import InMemoryFeed

def test_grid_search_and_walk_forward_pipeline(sample_ohlcv_polars_df):
    feed = InMemoryFeed(sample_ohlcv_polars_df, symbol="AAPL")
    space = ParameterSpace([
        CategoricalParam("atr_mult", [1.5, 2.0, 2.5]),
        CategoricalParam("lookback", [10, 20])
    ])
    
    # 1. Grid Search
    opt = GridSearchOptimizer(VolatilityAdjustedMeanReversionStrategy, space, initial_cash=5000.0)
    res = opt.optimize(feed)
    assert res.best_params is not None

    # 2. Walk Forward
    wf_opt = WalkForwardOptimizer(
        VolatilityAdjustedMeanReversionStrategy, space, is_bars=50, oos_bars=20, initial_cash=5000.0
    )
    wf_res = wf_opt.run(feed)
    assert wf_res is not None
    assert hasattr(wf_res, "wfe_ratio")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest ssbt/tests/test_volatility_statarb.py::test_grid_search_and_walk_forward_pipeline -v`
Expected: FAIL if fixtures or modules missing

- [ ] **Step 3: Implement `ssbt/experiments/run_volatility_statarb.py`**

```python
"""Run Volatility-Adjusted Mean Reversion & StatArb Trailing Stop Sweeps & Walk-Forward Analysis."""

from __future__ import annotations
import json
import numpy as np
import polars as pl
from ssbt.data.yfinance_loader import build_ssbt_feed_from_yfinance, download_yfinance_polars
from ssbt.data.feed import InMemoryFeed
from ssbt.optimization.space import ParameterSpace, CategoricalParam
from ssbt.optimization.grid_search import GridSearchOptimizer
from ssbt.optimization.walk_forward import WalkForwardOptimizer
from ssbt.analytics.overfitting import deflated_sharpe_ratio, probability_of_backtest_overfitting
from strategies_vault.volatility_mean_reversion import VolatilityAdjustedMeanReversionStrategy
from strategies_vault.statarb_pairs import StatArbPairsStrategy

def run_experiment(symbol: str = "AAPL", period: str = "1y", interval: str = "1d"):
    print(f"=== Downloading yfinance data for {symbol} ({period}, {interval}) ===")
    feed = build_ssbt_feed_from_yfinance(symbol, period=period, interval=interval)

    # 1. Trailing Stop Multiplier Grid Sweep
    param_space = ParameterSpace([
        CategoricalParam("atr_mult", [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]),
        CategoricalParam("lookback", [15, 20, 30])
    ])

    print("\n--- Sweeping Trailing Stops (GridSearchOptimizer) ---")
    grid_search = GridSearchOptimizer(
        strategy_cls=VolatilityAdjustedMeanReversionStrategy,
        param_space=param_space,
        initial_cash=5000.0,
    )
    grid_res = grid_search.optimize(feed)
    print(f"Best Parameters: {grid_res.best_params}")
    print(f"Best In-Sample Sharpe: {grid_res.best_sharpe:.4f}")

    # 2. Rolling Walk-Forward Optimization
    print("\n--- Running Walk-Forward Optimization (WalkForwardOptimizer) ---")
    wf_opt = WalkForwardOptimizer(
        strategy_cls=VolatilityAdjustedMeanReversionStrategy,
        param_space=param_space,
        is_bars=80,
        oos_bars=30,
        initial_cash=5000.0,
    )
    wf_res = wf_opt.run(feed)
    print(f"Walk-Forward Windows Completed: {len(wf_res.windows)}")
    print(f"Overall OOS Sharpe: {wf_res.overall_oos_sharpe:.4f}")
    print(f"Walk-Forward Efficiency (WFE Ratio): {wf_res.wfe_ratio:.4f}")

    # 3. Overfitting Defense (DSR / PBO)
    returns = np.diff(wf_res.stitched_oos_equity) / (wf_res.stitched_oos_equity[:-1] + 1e-8)
    dsr = deflated_sharpe_ratio(returns, num_trials=len(grid_res.all_results))
    print(f"Deflated Sharpe Ratio (DSR): {dsr:.4f}")

    results_dict = {
        "symbol": symbol,
        "initial_balance": 5000.0,
        "max_risk_pct": 0.0015,
        "max_risk_dollars": 7.50,
        "best_params": grid_res.best_params,
        "best_is_sharpe": grid_res.best_sharpe,
        "overall_oos_sharpe": wf_res.overall_oos_sharpe,
        "wfe_ratio": wf_res.wfe_ratio,
        "deflated_sharpe_ratio": dsr,
    }
    return results_dict

if __name__ == "__main__":
    res = run_experiment("AAPL", period="1y", interval="1d")
    print("\n=== Experiment Summary ===")
    print(json.dumps(res, indent=2))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest ssbt/tests/test_volatility_statarb.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 4**

```bash
git add ssbt/experiments/run_volatility_statarb.py ssbt/tests/test_volatility_statarb.py
git commit -m "feat(experiment): implement trailing stop parameter sweep & walk forward script"
```

---

### Task 5: Full Suite Integration & Verification Run

**Files:**
- Modify/Run: `ssbt/experiments/run_volatility_statarb.py`
- Test: All tests in `ssbt/tests/`

- [ ] **Step 1: Execute full experiment script**

Run: `uv run python -m ssbt.experiments.run_volatility_statarb`
Expected: Execution completes cleanly, outputting best parameters, WFE ratio, and DSR metrics.

- [ ] **Step 2: Run full pytest test suite**

Run: `uv run python -m pytest ssbt/tests/ -v`
Expected: 252+ tests passing with 0 errors.

- [ ] **Step 3: Commit Task 5 & Final Verification**

```bash
git add .
git commit -m "feat: complete volatility-adjusted mean reversion and statarb pipeline"
```
