"""Adapter for positioning backtesting as a specialized exploration experiment."""

from __future__ import annotations

from typing import Any
import numpy as np
import polars as pl

from ssbt.analytics.metrics import compute_metrics
from ssbt.core.engine import Engine
from ssbt.data.feed import InMemoryFeed, ParquetFeed


class BacktestAdapter:
    """Adapts SSBT Backtest Engine execution to unified experiment schema."""

    def __init__(self, initial_cash: float = 100_000.0) -> None:
        self.initial_cash = initial_cash

    def run_backtest(self, feed: ParquetFeed | InMemoryFeed, strategy: Any) -> dict[str, Any]:
        """Run engine and return standardized metrics, equity curve, and trades as DataFrames."""
        engine = Engine(feed=feed, strategy=strategy, initial_cash=self.initial_cash)
        result = engine.run()
        metrics = compute_metrics(result.equity_curve, result.trades)

        trade_rows = []
        for t in result.trades:
            denom = t.entry_price * t.qty
            pnl_pct = (t.pnl / denom) if denom != 0 else 0.0
            trade_rows.append({
                "symbol": t.symbol,
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "qty": t.qty,
                "side": t.side.name if hasattr(t.side, "name") else str(t.side),
                "pnl": t.pnl,
                "pnl_pct": pnl_pct,
                "commission": t.commission,
            })
        trades_df = pl.DataFrame(trade_rows) if trade_rows else pl.DataFrame(schema={
            "symbol": pl.Utf8,
            "entry_time": pl.Int64,
            "exit_time": pl.Int64,
            "entry_price": pl.Float64,
            "exit_price": pl.Float64,
            "qty": pl.Float64,
            "side": pl.Utf8,
            "pnl": pl.Float64,
            "pnl_pct": pl.Float64,
            "commission": pl.Float64,
        })

        return {
            "initial_cash": self.initial_cash,
            "final_equity": result.final_equity,
            "total_return": result.total_return,
            "equity_curve": result.equity_curve,
            "metrics": metrics,
            "trades": trades_df,
            "raw_result": result,
        }
