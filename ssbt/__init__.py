"""SSBT — Super Speedy Backtesting Tool & Generic Exploration Engine."""

from ssbt.core.engine import Engine, BacktestResult
from ssbt.core.events import (
    Bar, BidAsk, Order, Fill, Trade,
    Side, OrderType, OrderStatus, TimeInForce,
)
from ssbt.core.matching import MatchingEngine
from ssbt.core.portfolio import Portfolio
from ssbt.core.vectorised import VectorisedBacktester, VectorisedStrategy
from ssbt.core.multi_engine import MultiSymbolEngine
from ssbt.core._numba_kernels import HAS_NUMBA
from ssbt.data.feed import InMemoryFeed, ParquetFeed
from ssbt.data.live import LiveStreamFeed, QueueOverflowPolicy
from ssbt.exceptions import SSBTError, DataError, ExecutionError, AuditError
from ssbt.strategy.base import Strategy
from ssbt.strategy.live_runner import LiveStrategyRunner
from ssbt.execution import (
    QueuePriorityModel, ExecutionLatencyModel, L3MatchingEngine, QueueOrderTracker,
)
from ssbt.optimization import (
    ParameterSpace, ParamRange, IntParam, FloatParam, ChoiceParam,
    GridSearchOptimizer, OptimizationResult, WalkForwardOptimizer, WalkForwardResult, WalkForwardWindow,
)
from ssbt.strategy.base import Strategy
from ssbt.portfolio.allocation import (
    AllocationFn, equal_weight, inverse_volatility, custom_allocation,
)
from ssbt.analytics.optimization import (
    param_grid, run_sweep, run_matrix_sweep, results_to_dataframe, SweepResult,
    walk_forward, BaseOptimizer, GridSearch,
)
from ssbt.analytics.metrics import compute_metrics, format_metrics, compute_tradingview_overview
from ssbt.analytics.plots import (
    plot_equity_curve, plot_drawdown, plot_trades,
    plot_strategy_dashboard, plot_tradingview_dashboard,
    plot_robustness_dashboard, plot_performance_metrics, plot_walk_forward_dashboard,
    plot_l3_orderbook_dashboard,
    plot, autoplot,
)
from ssbt.events.base import BaseEvent
from ssbt.outcomes.base import BaseOutcome
from ssbt.experiments.specs import ExperimentSpec
from ssbt.experiments.loader import load_experiment, LoaderError
from ssbt.experiments.runner import run_experiment, RunnerError
from ssbt.experiments.registry import Registry, RegistryError
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.experiments.reproducibility import capture_environment_snapshot
from ssbt.data.point_in_time import align_multi_timeframe, validate_point_in_time_join, CausalityViolationError
from ssbt.data.orderbook import rebuild_orderbook_from_bars, OrderBookEngine, OrderBookFeed, OrderBookQuote
from ssbt.data.universal_tick import UniversalTickStream, UniversalTickFeed
from ssbt.analytics.audit import AuditLogger, sync_latest_run_folder, AuditReport
from ssbt.analytics.stream import (
    ExecutionStreamPublisher, StreamEvent, StreamEventType,
    IPCSink, BufferedFileSink, CallbackIPCSink, QueueIPCSink, SocketIPCSink,
    RingBufferIPCSink, BinaryIPCSink,
)
from ssbt.analytics.robustness import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    monte_carlo_trade_permutation,
)
from ssbt.execution.models import (
    ImpactModel,
    LiquidityCapModel,
    BorrowCostModel,
    RealisticExecutionEngine,
)
from ssbt.portfolio.risk import (
    VolatilityTargetingOverlay,
    StrategyCapacityAnalyzer,
)
from ssbt.analytics.terminal import (
    display_experiment_summary,
    display_backtest_summary,
    display_audit_status,
)
from ssbt.experiments.charts import (
    generate_all_charts,
    generate_distribution_chart,
    generate_grouped_bar_chart,
    generate_event_timeline_chart,
    generate_matrix_heatmap_chart,
    generate_multi_equity_curve_chart,
)

from ssbt.quick import (
    quick_backtest,
    QuickResult,
    strategy,
    generate_synthetic_bars,
)
from ssbt.agent import (
    get_experiment_schema,
    validate_strategy_script,
    get_agent_template,
)
from ssbt.service import (
    run_backtest,
    run_backtest_async,
    rerun,
    compare,
    BacktestRequest,
    BacktestResponse,
    StrategySpec,
    DataSpec,
    ExecutionSpec,
    ResourceLimitSpec,
    ServiceError,
    E_DATA_SCHEMA,
    E_STRATEGY_INIT,
    E_RESOURCE_LIMIT,
    E_LOOKAHEAD,
    E_RUN_NOT_FOUND,
    explain_failure,
    get_agent_tool_spec,
)

__version__ = "0.5.0"

__all__ = [
    # Core Engine
    "Engine", "BacktestResult", "MultiSymbolEngine",
    "VectorisedBacktester", "VectorisedStrategy",
    "ParquetFeed", "InMemoryFeed", "LiveStreamFeed", "QueueOverflowPolicy", "MatchingEngine", "Portfolio", "Strategy", "LiveStrategyRunner",
    "Bar", "BidAsk", "Order", "Fill", "Trade",
    "Side", "OrderType", "OrderStatus", "TimeInForce",
    "AllocationFn", "equal_weight", "inverse_volatility", "custom_allocation",
    "param_grid", "run_sweep", "run_matrix_sweep", "results_to_dataframe", "SweepResult",
    "walk_forward", "WalkForwardResult", "WalkForwardWindow",
    "BaseOptimizer", "GridSearch",
    "compute_metrics", "format_metrics", "HAS_NUMBA",
    # Ergonomics & Agent Tooling
    "quick_backtest", "QuickResult", "strategy", "generate_synthetic_bars",
    "get_experiment_schema", "validate_strategy_script", "get_agent_template",
    # Exploration Engine & Plugins
    "BaseEvent", "BaseOutcome", "ExperimentSpec",
    "load_experiment", "LoaderError",
    "run_experiment", "RunnerError",
    "Registry", "RegistryError",
    "BacktestAdapter",
    # Audit, Overfitting Defense, Microstructure & IPC Streaming
    "AuditLogger", "AuditReport",
    "ExecutionStreamPublisher", "StreamEvent", "StreamEventType",
    "IPCSink", "BufferedFileSink", "CallbackIPCSink", "QueueIPCSink", "SocketIPCSink",
    "RingBufferIPCSink", "BinaryIPCSink",
    "deflated_sharpe_ratio", "probability_of_backtest_overfitting", "monte_carlo_trade_permutation",
    "ImpactModel", "LiquidityCapModel", "BorrowCostModel", "RealisticExecutionEngine",
    "VolatilityTargetingOverlay", "StrategyCapacityAnalyzer",
    "generate_all_charts", "generate_matrix_heatmap_chart", "generate_multi_equity_curve_chart",
    "display_experiment_summary", "display_backtest_summary", "display_audit_status",
    # Engine Service Core
    "run_backtest", "run_backtest_async", "rerun", "compare",
    "BacktestRequest", "BacktestResponse", "StrategySpec", "DataSpec",
    "ExecutionSpec", "ResourceLimitSpec", "ServiceError",
    "E_DATA_SCHEMA", "E_STRATEGY_INIT", "E_RESOURCE_LIMIT", "E_LOOKAHEAD", "E_RUN_NOT_FOUND",
    "explain_failure", "get_agent_tool_spec",
]

