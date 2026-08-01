# SSBT — Super Speedy Backtesting Tool (Context7 / AI Agent Reference)

> **Library ID**: `ssbt`  
> **Package**: `ssbt` (PyPI v0.5.0)  
> **Type**: High-Performance Event-Driven Backtesting & Statistical Exploration Framework  
> **Python Version**: `>=3.10`  
> **Core Dependencies**: `polars>=0.20`, `numpy>=1.24`, `matplotlib>=3.7`, `numba>=0.66.0`

---

## 1. Quick Start & Ergonomics (`ssbt.quick`)

The quickest way for AI agents to run backtests or prototype strategies using inline source code or DataFrames.

```python
import polars as pl
from ssbt import quick_backtest, strategy, generate_synthetic_bars, Side, OrderType

# Generate synthetic test data (or provide custom Polars DataFrame)
df = generate_synthetic_bars(num_bars=1000, start_price=100.0, volatility=0.01)

# Define strategy using decorator
@strategy(name="SMA_Cross")
def sma_cross(self, engine, bar):
    """Simple Moving Average Crossover Strategy."""
    closes = self.get_history(engine, bar.symbol, "close", 20)
    if len(closes) < 20:
        return

    sma_short = sum(closes[-5:]) / 5
    sma_long = sum(closes[-20:]) / 20

    pos_qty = self.get_position_qty(engine, bar.symbol)

    if sma_short > sma_long and pos_qty <= 0:
        self.buy(engine, bar.symbol, qty=10.0, order_type=OrderType.MARKET)
    elif sma_short < sma_long and pos_qty > 0:
        self.sell(engine, bar.symbol, qty=10.0, order_type=OrderType.MARKET)

# Run fast backtest
result = quick_backtest(df, sma_cross, initial_cash=100_000.0)
print(result.summary())
```

---

## 2. Object-Oriented Strategy Base (`ssbt.strategy.base.Strategy`)

Class-based strategies subclassing `ssbt.Strategy` for full lifecycle control.

```python
from ssbt import Strategy, Side, OrderType, TimeInForce

class MeanReversionStrategy(Strategy):
    def __init__(self, window: int = 20, num_std: float = 2.0):
        super().__init__(name="MeanReversion")
        self.window = window
        self.num_std = num_std

    def on_start(self, engine):
        """Called once prior to bar iteration."""
        self.log("Strategy initialized")

    def on_bar(self, engine, bar):
        """Executed per tick/bar event in point-in-time sequence."""
        closes = self.get_history(engine, bar.symbol, "close", self.window)
        if len(closes) < self.window:
            return

        mean = sum(closes) / len(closes)
        variance = sum((x - mean) ** 2 for x in closes) / len(closes)
        std = variance ** 0.5

        upper_band = mean + self.num_std * std
        lower_band = mean - self.num_std * std

        pos_qty = self.get_position_qty(engine, bar.symbol)

        if bar.close < lower_band and pos_qty <= 0:
            self.cancel_all_orders(engine, bar.symbol)
            self.buy(engine, bar.symbol, qty=100.0, order_type=OrderType.LIMIT, price=bar.close * 0.999)
        elif bar.close > upper_band and pos_qty >= 0:
            self.cancel_all_orders(engine, bar.symbol)
            self.sell(engine, bar.symbol, qty=100.0, order_type=OrderType.LIMIT, price=bar.close * 1.001)

    def on_stop(self, engine):
        """Called upon completion of backtest simulation."""
        self.log("Strategy run finished")
```

---

## 3. High-Level Engine Execution (`ssbt.Engine` & `ssbt.InMemoryFeed`)

Executing backtests directly with full feed control and transaction logging.

```python
import polars as pl
from ssbt import Engine, InMemoryFeed, BaseEvent

# 1. Prepare Data
df = pl.read_parquet("market_data.parquet") # Must contain: timestamp, open, high, low, close, volume, symbol
feed = InMemoryFeed(df, symbol="BTC-USD")

# 2. Setup Engine & Strategy
strategy = MeanReversionStrategy(window=30, num_std=2.5)
engine = Engine(
    feed=feed,
    strategy=strategy,
    initial_cash=1_000_000.0,
    slippage=0.0001,      # 1 bps slippage
    fee_rate=0.0005,      # 5 bps trading commission
    fill_on_next_bar=True # Realistic next-bar execution (anti-lookahead)
)

# 3. Run Simulation
results = engine.run()

# 4. Extract Performance
print(f"Total Return: {results.total_return * 100:.2f}%")
print(f"Sharpe Ratio: {results.sharpe_ratio:.2f}")
print(f"Max Drawdown: {results.max_drawdown * 100:.2f}%")
```

---

## 4. Multi-Symbol & Portfolio Allocation (`ssbt.MultiSymbolEngine`)

Backtesting strategies across multiple symbols with portfolio rebalancing.

```python
from ssbt import MultiSymbolEngine, InMemoryFeed, equal_weight, inverse_volatility

# Build multi-asset feed
feed = InMemoryFeed(df_multi) # DataFrame containing multiple symbols

engine = MultiSymbolEngine(
    feed=feed,
    strategy=my_multi_asset_strategy,
    initial_cash=500_000.0,
    allocation_fn=inverse_volatility, # equal_weight or custom allocation function
)

results = engine.run()
```

---

## 5. Statistical Overfitting Defense (`ssbt.analytics.robustness`)

Institutional quantitative defense against data mining and overfitting.

```python
from ssbt import deflated_sharpe_ratio, probability_of_backtest_overfitting, monte_carlo_trade_permutation

# 1. Deflated Sharpe Ratio (DSR) - adjusts Sharpe for multiple testing / trial count
dsr = deflated_sharpe_ratio(
    observed_sharpe=1.8,
    returns_series=results.returns,
    num_trials=100 # Total strategy iterations tested
)
print(f"Deflated Sharpe Ratio p-value: {dsr:.4f}")

# 2. Probability of Backtest Overfitting (PBO)
pbo = probability_of_backtest_overfitting(
    matrix_returns=all_strategy_returns_matrix,
    n_splits=10
)
print(f"PBO Score: {pbo * 100:.1f}%")

# 3. Monte Carlo Trade Sequence Permutation
mc_metrics = monte_carlo_trade_permutation(
    trades=results.trades,
    num_simulations=1000,
    confidence_level=0.95
)
print(f"95% Value at Risk (VaR): {mc_metrics['var_95']:.4f}")
```

---

## 6. Point-in-Time Integrity & Microstructure Modeling

```python
from ssbt import align_multi_timeframe, validate_point_in_time_join, RealisticExecutionEngine, ImpactModel

# Align higher timeframe data without lookahead leakage
aligned_df = align_multi_timeframe(
    low_tf_df=1m_bars,
    high_tf_df=1h_indicators,
    on="timestamp"
)

# Apply realistic market microstructure adverse fill execution
execution_model = RealisticExecutionEngine(
    impact_model=ImpactModel.SQUARE_ROOT,
    max_participation=0.05, # Max 5% volume participation
    borrow_rate_annual=0.02
)
```

---

## 7. Engine Service API (`ssbt.service`)

Asynchronous job execution, profiling, and diagnostics.

```python
from ssbt.service import run_backtest, BacktestRequest, StrategySpec, DataSpec

request = BacktestRequest(
    strategy=StrategySpec(name="MeanReversion", params={"window": 20}),
    data=DataSpec(dataset_id="BTC-USD-1M"),
    initial_cash=100000.0
)

response = run_backtest(request)
print(f"Status: {response.status}, Run ID: {response.run_id}")
```

---

## Key Enums & Symbols

- `Side.BUY`, `Side.SELL`
- `OrderType.MARKET`, `OrderType.LIMIT`, `OrderType.STOP_LOSS`, `OrderType.TAKE_PROFIT`
- `OrderStatus.PENDING`, `OrderStatus.FILLED`, `OrderStatus.PARTIALLY_FILLED`, `OrderStatus.CANCELLED`
- `TimeInForce.GTC`, `TimeInForce.IOC`, `TimeInForce.FOK`
