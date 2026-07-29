"""Grid Search Parameter Optimizer with Overfitting Auditing."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Type
import numpy as np
import polars as pl

from ssbt.strategy.base import Strategy
from ssbt.data.feed import InMemoryFeed
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.analytics.robustness import deflated_sharpe_ratio, probability_of_backtest_overfitting
from ssbt.optimization.space import ParameterSpace


@dataclass
class OptimizationResult:
    """Dataclass holding complete parameter optimization trial metrics."""
    best_params: dict[str, Any]
    best_sharpe: float
    all_trials: list[dict[str, Any]]
    dsr_score: float
    pbo_score: float


class GridSearchOptimizer:
    """Executes systematic parameter grid search over strategy classes."""

    def __init__(
        self,
        strategy_cls: Type[Strategy],
        param_space: ParameterSpace,
        initial_cash: float = 5000.0,
    ):
        self.strategy_cls = strategy_cls
        self.param_space = param_space
        self.initial_cash = initial_cash

    def optimize(self, feed: InMemoryFeed) -> OptimizationResult:
        """Run grid search evaluation across all parameter combinations."""
        grid = self.param_space.generate_grid()
        trials: list[dict[str, Any]] = []
        returns_list: list[np.ndarray] = []

        best_params = {}
        best_sharpe = -999.0

        for params in grid:
            # Instantiate strategy with kwargs
            strat = self.strategy_cls(**params)
            adapter = BacktestAdapter(initial_cash=self.initial_cash)
            res = adapter.run_backtest(feed, strat)

            raw = res["raw_result"]
            metrics = res.get("metrics", {})
            sharpe = metrics.get("sharpe", raw.total_return)
            net_pnl = metrics.get("net_profit", raw.final_equity - self.initial_cash)
            max_dd = metrics.get("max_drawdown", 0.0)

            # Store returns for PBO computation
            eq = raw.equity_curve
            if len(eq) > 1:
                eq_arr = eq[:, 1]
                rets = np.diff(eq_arr) / (eq_arr[:-1] + 1e-8)
                returns_list.append(rets)

            trials.append({
                "params": params,
                "sharpe": sharpe,
                "net_pnl": net_pnl,
                "max_dd": max_dd,
                "total_trades": len(raw.trades),
            })

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = params

        # Calculate DSR across trials
        all_sharpes = [t["sharpe"] for t in trials]
        var_sharpe = float(np.var(all_sharpes)) if len(all_sharpes) > 1 else 0.10
        dsr = deflated_sharpe_ratio(
            observed_sharpe=max(best_sharpe, 0.0),
            var_sharpes=max(var_sharpe, 0.01),
            n_trials=len(trials),
            returns_len=len(feed.df),
        )

        # Calculate PBO across trials matrix
        pbo = 0.0
        if len(returns_list) > 1:
            min_len = min(len(r) for r in returns_list)
            if min_len > 10:
                ret_mat = np.column_stack([r[:min_len] for r in returns_list])
                pbo = probability_of_backtest_overfitting(ret_mat)

        return OptimizationResult(
            best_params=best_params,
            best_sharpe=best_sharpe,
            all_trials=trials,
            dsr_score=dsr,
            pbo_score=pbo,
        )
