# SSBT Core Reference API (`ssbt.core` & `ssbt.strategy`)

---
summary: Reference documentation for core SSBT classes including Engine, Strategy, Order, Fill, Trade, and BacktestResult.
keywords: reference, core, Engine, Strategy, Order, OrderType, Side, BacktestResult
domain: api-reference
difficulty: intermediate
primary_apis: ssbt.Engine, ssbt.Strategy, ssbt.Order, ssbt.Fill, ssbt.BacktestResult
related_pages: /docs/index.md, /docs/reference/index.md, /docs/use-cases/single-asset-mean-reversion.md
---

## `ssbt.Engine`

Main execution orchestrator running event-driven backtests over data feeds.

```python
class Engine:
    def __init__(
        self,
        feed: BaseFeed,
        execution_engine: BaseExecutionEngine = None,
        portfolio: Portfolio = None,
        audit_logger: AuditLogger = None,
        stream_publisher: ExecutionStreamPublisher = None
    )
```

### Parameters
- `feed` (`BaseFeed`): Data feed provider (e.g. `InMemoryFeed`, `ParquetFeed`).
- `execution_engine` (`BaseExecutionEngine`, optional): Execution simulator (defaults to conservative `MatchingEngine`).
- `portfolio` (`Portfolio`, optional): Cash and position state tracker (defaults to `$100,000` initial cash).
- `audit_logger` (`AuditLogger`, optional): Point-in-time causality audit recorder.
- `stream_publisher` (`ExecutionStreamPublisher`, optional): Live IPC telemetry publisher.

### Methods

#### `run(strategy: Strategy) -> BacktestResult`
Executes full backtest simulation for the provided strategy instance.
- **Return Contract**: `BacktestResult` object containing metrics, fills, trades, and equity curve.
- **Determinism**: 100% deterministic given identical inputs and RNG seeds.
- **Exceptions**: `ValueError` if feed is empty or un-sorted.

---

## `ssbt.Strategy`

Base class for object-oriented trading strategies.

```python
class Strategy:
    def __init__(self, name: str = "BaseStrategy")
```

### Lifecycle Callbacks
- `on_start(self, engine: Engine)`: Triggered once prior to bar processing.
- `on_bar(self, engine: Engine, bar: Bar)`: Triggered for every point-in-time bar event.
- `on_order_status(self, engine: Engine, order: Order)`: Triggered when an order state changes (fill, partial fill, cancellation).
- `on_stop(self, engine: Engine)`: Triggered after simulation completion.

### Helper Methods
- `buy(engine, symbol: str, qty: float, order_type: OrderType = OrderType.MARKET, price: float = None) -> Order`
- `sell(engine, symbol: str, qty: float, order_type: OrderType = OrderType.MARKET, price: float = None) -> Order`
- `cancel_order(engine, order_id: str)`
- `cancel_all_orders(engine, symbol: str)`
- `get_position_qty(engine, symbol: str) -> float`
- `is_flat(engine, symbol: str) -> bool`
- `get_history(engine, symbol: str, column: str, N: int) -> List[float]`

---

## `ssbt.Order`

Dataclass representing an order request.

### Enums
- `Side`: `BUY`, `SELL`
- `OrderType`: `MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT`, `TRAILING_STOP`
- `OrderStatus`: `PENDING`, `FILLED`, `PARTIALLY_FILLED`, `CANCELLED`
- `TimeInForce`: `GTC`, `IOC`, `FOK`
