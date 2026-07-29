"""Rolling Walk-Forward Parameter Optimizer with Out-of-Sample Stitching."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Type
import numpy as np
import polars as pl

from ssbt.strategy.base import Strategy
from ssbt.data.feed import InMemoryFeed
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.optimization.space import ParameterSpace
from ssbt.optimization.grid_search import GridSearchOptimizer


@dataclass
class WalkForwardWindow:
    """Represents a single walk-forward train (In-Sample) and test (Out-of-Sample) window."""
    window_index: int
    is_start: int
    is_end: int
    oos_start: int
    oos_end: int
    best_params: dict[str, Any]
    is_sharpe: float
    oos_sharpe: float
    oos_equity_curve: np.ndarray


@dataclass
class WalkForwardResult:
    """Container for complete Walk-Forward optimization results."""
    windows: list[WalkForwardWindow]
    stitched_oos_equity: np.ndarray
    wfe_ratio: float  # Walk-Forward Efficiency Ratio (OOS Sharpe / IS Sharpe)
    overall_oos_sharpe: float


class WalkForwardOptimizer:
    """Executes rolling walk-forward optimization across market data feeds."""

    def __init__(
        self,
        strategy_cls: Type[Strategy],
        param_space: ParameterSpace,
        is_bars: int = 200,
        oos_bars: int = 50,
        initial_cash: float = 5000.0,
    ):
        self.strategy_cls = strategy_cls
        self.param_space = param_space
        self.is_bars = is_bars
        self.oos_bars = oos_bars
        self.initial_cash = initial_cash

    def run(self, feed: InMemoryFeed) -> WalkForwardResult:
        """Run rolling In-Sample / Out-of-Sample walk-forward optimization."""
        df = feed.df
        total_bars = len(df)

        if total_bars < (self.is_bars + self.oos_bars):
            raise ValueError(
                f"Insufficient data for Walk-Forward: Total bars ({total_bars}) < "
                f"IS bars ({self.is_bars}) + OOS bars ({self.oos_bars})"
            )

        windows: list[WalkForwardWindow] = []
        stitched_equity = [self.initial_cash]
        current_cash = self.initial_cash

        win_idx = 0
        is_start = 0

        while (is_start + self.is_bars + self.oos_bars) <= total_bars:
            is_end = is_start + self.is_bars
            oos_start = is_end
            oos_end = oos_start + self.oos_bars

            sym = feed.symbols[0] if feed.symbols else "ASSET"
            # 1. Extract In-Sample Polars slice & run GridSearch
            is_df = df.slice(is_start, self.is_bars)
            is_feed = InMemoryFeed(is_df, symbol=sym)
            grid_opt = GridSearchOptimizer(
                strategy_cls=self.strategy_cls,
                param_space=self.param_space,
                initial_cash=current_cash,
            )
            is_res = grid_opt.optimize(is_feed)

            # 2. Evaluate best params on Out-of-Sample slice
            oos_df = df.slice(oos_start, self.oos_bars)
            oos_feed = InMemoryFeed(oos_df, symbol=sym)
            best_strat = self.strategy_cls(**is_res.best_params)
            adapter = BacktestAdapter(initial_cash=current_cash)
            oos_backtest = adapter.run_backtest(oos_feed, best_strat)

            oos_raw = oos_backtest["raw_result"]
            oos_metrics = oos_backtest.get("metrics", {})
            oos_sharpe = oos_metrics.get("sharpe", oos_raw.total_return)
            oos_eq = oos_raw.equity_curve[:, 1] if len(oos_raw.equity_curve) > 0 else np.array([current_cash])

            # Update stitched equity
            if len(oos_eq) > 1:
                # Add incremental changes to current cash
                inc = np.diff(oos_eq)
                for val in inc:
                    current_cash += val
                    stitched_equity.append(current_cash)

            windows.append(WalkForwardWindow(
                window_index=win_idx,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
                best_params=is_res.best_params,
                is_sharpe=is_res.best_sharpe,
                oos_sharpe=oos_sharpe,
                oos_equity_curve=oos_eq,
            ))

            win_idx += 1
            is_start += self.oos_bars  # Roll window forward by OOS bar step

        # Compute overall OOS metrics
        stitched_arr = np.array(stitched_equity)
        rets = np.diff(stitched_arr) / (stitched_arr[:-1] + 1e-8) if len(stitched_arr) > 1 else np.array([0.0])
        overall_oos_sharpe = float(np.mean(rets) / (np.std(rets) + 1e-8) * np.sqrt(252)) if len(rets) > 1 else 0.0

        avg_is_sharpe = float(np.mean([w.is_sharpe for w in windows])) if windows else 1.0
        wfe_ratio = float(overall_oos_sharpe / max(avg_is_sharpe, 1e-5))

        return WalkForwardResult(
            windows=windows,
            stitched_oos_equity=stitched_arr,
            wfe_ratio=wfe_ratio,
            overall_oos_sharpe=overall_oos_sharpe,
        )
