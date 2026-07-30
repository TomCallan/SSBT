# Design Spec: Volatility-Adjusted Mean Reversion & Statistical Arbitrage Pipeline

## 1. Overview
This specification details the implementation of a Volatility-Adjusted Mean Reversion strategy and a Statistical Arbitrage Pairs Trading strategy built strictly on top of the SSBT quantitative backtesting framework.

Key constraints & requirements:
- Data Downloading: Downloads OHLCV data using `yfinance` for multiple instruments across resolutions (1-day, 1-hour), format into Polars `pl.DataFrame` and feeds directly into SSBT's `InMemoryFeed`.
- Isolated Balance: Each instrument or pair receives an independent initial balance of $5,000.
- Risk Limit: Maximum risk per trade is strictly capped at 0.15% of initial account balance ($7.50).
- Trailing Stop Sweeping: Executes grid search parameter sweeps across ATR trailing stop multipliers.
- Walk-Forward Analysis: Employs SSBT's rolling `WalkForwardOptimizer` to test Out-Of-Sample (OOS) performance, stitching equity curves, calculating Walk-Forward Efficiency (WFE ratio), and evaluating overfitting metrics (Deflated Sharpe Ratio / PBO).

---

## 2. Architecture & Component Interaction

```
 yfinance Download -> Polars DataFrame -> SSBT InMemoryFeed -> Strategy Engine -> Grid Search & Walk-Forward
```

### Data Pipeline
1. `ssbt/data/yfinance_loader.py`: Downloader utility fetching market data via `yfinance`, standardizing schema to `timestamp`, `open`, `high`, `low`, `close`, `volume`, `symbol`, and returning Polars DataFrames.

### Strategy Vault Implementations
1. `strategies_vault/volatility_mean_reversion.py`: `VolatilityAdjustedMeanReversionStrategy`
   - $N$-period rolling mean & standard deviation for Z-score calculation ($Z = \frac{P - \mu}{\sigma}$).
   - ATR volatility indicator for dynamic risk-based sizing and trailing stop calculation.
   - Per-trade risk cap: $\$5,000 \times 0.0015 = \$7.50$.
   - Stop Distance: $D_{\text{stop}} = \text{mult}_{\text{ATR}} \times \text{ATR}$.
   - Position Quantity: $Q = \text{max}(1, \lfloor \frac{7.50}{D_{\text{stop}}} \rfloor)$.
   - Submits entry market order paired with `OrderType.TRAILING_STOP` with `trail_offset = D_{\text{stop}}`.

2. `strategies_vault/statarb_pairs.py`: `StatArbPairsStrategy`
   - Rolling OLS linear regression between pair asset $P_1$ and asset $P_2$ to calculate hedge ratio $\beta$: $\text{Spread}_t = P_{1,t} - \beta \cdot P_{2,t}$.
   - Z-score of spread: $Z_{\text{spread}} = \frac{\text{Spread}_t - \mu_{\text{spread}}}{\sigma_{\text{spread}}}$.
   - Entry triggers on extreme spread Z-score ($\le -Z_{\text{entry}}$ or $\ge Z_{\text{entry}}$).
   - ATR trailing stop on spread volatility to manage drawdown.

### Parameter Optimization & Walk-Forward Suite
1. `ssbt/experiments/run_volatility_statarb.py`:
   - Configures parameter grid sweeps over trailing stop multipliers ($1.0\times$ to $3.5\times$ ATR).
   - Runs SSBT `GridSearchOptimizer` and `WalkForwardOptimizer` with rolling IS/OOS windows.
   - Calculates stitched OOS equity curve, overall OOS Sharpe ratio, WFE ratio, DSR, and PBO.
   - Saves execution artifacts and diagnostic outputs.

---

## 3. Test & Verification Plan
- Unit tests in `ssbt/tests/test_volatility_statarb.py`:
  - Test `yfinance_loader` DataFrame schema & timestamp alignment.
  - Test `VolatilityAdjustedMeanReversionStrategy` order generation, risk sizing ($7.50 cap), and trailing stop creation.
  - Test `StatArbPairsStrategy` spread Z-score computation and position execution.
  - Test `GridSearchOptimizer` trailing stop parameter sweep.
  - Test `WalkForwardOptimizer` run completion and stitched equity output.
- Integration tests: Full end-to-end backtest on synthetic and yfinance real data.
