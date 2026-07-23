"""SSBT — Super Simple Backtesting Tool."""

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

__version__ = "0.4.0"

__all__ = [
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
]
