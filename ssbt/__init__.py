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
from ssbt.strategy.base import Strategy
from ssbt.portfolio.allocation import (
    AllocationFn, equal_weight, inverse_volatility, custom_allocation,
)
from ssbt.analytics.optimization import (
    param_grid, run_sweep, run_matrix_sweep, results_to_dataframe, SweepResult,
    walk_forward, WalkForwardResult, WalkForwardWindow,
    BaseOptimizer, GridSearch,
)
from ssbt.analytics.metrics import compute_metrics, format_metrics
from ssbt.events.base import BaseEvent
from ssbt.outcomes.base import BaseOutcome
from ssbt.experiments.specs import ExperimentSpec
from ssbt.experiments.loader import load_experiment, LoaderError
from ssbt.experiments.runner import run_experiment, RunnerError
from ssbt.experiments.registry import Registry, RegistryError
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.analytics.audit import AuditLogger, AuditReport
from ssbt.analytics.stream import ExecutionStreamPublisher, StreamEvent
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

__version__ = "0.4.0"

__all__ = [
    # Core Engine
    "Engine", "BacktestResult", "MultiSymbolEngine",
    "VectorisedBacktester", "VectorisedStrategy",
    "ParquetFeed", "InMemoryFeed", "MatchingEngine", "Portfolio", "Strategy",
    "Bar", "BidAsk", "Order", "Fill", "Trade",
    "Side", "OrderType", "OrderStatus", "TimeInForce",
    "AllocationFn", "equal_weight", "inverse_volatility", "custom_allocation",
    "param_grid", "run_sweep", "run_matrix_sweep", "results_to_dataframe", "SweepResult",
    "walk_forward", "WalkForwardResult", "WalkForwardWindow",
    "BaseOptimizer", "GridSearch",
    "compute_metrics", "format_metrics", "HAS_NUMBA",
    # Exploration Engine & Plugins
    "BaseEvent", "BaseOutcome", "ExperimentSpec",
    "load_experiment", "LoaderError",
    "run_experiment", "RunnerError",
    "Registry", "RegistryError",
    "BacktestAdapter",
    # Audit, Real-Time Stream, Charts & Terminal Displays
    "AuditLogger", "AuditReport",
    "ExecutionStreamPublisher", "StreamEvent",
    "generate_all_charts", "generate_matrix_heatmap_chart", "generate_multi_equity_curve_chart",
    "display_experiment_summary", "display_backtest_summary", "display_audit_status",
]
