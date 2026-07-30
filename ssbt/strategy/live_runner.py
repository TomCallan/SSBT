"""Live Strategy Runner — State persistence, checkpointing, and parameter hot-reloading.

Manages live strategy execution loops, enabling zero-downtime parameter adjustments
and crash recovery via JSON state checkpoints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ssbt.core.engine import Engine, BacktestResult
from ssbt.core.portfolio import Position
from ssbt.data.live import LiveStreamFeed
from ssbt.strategy.base import Strategy


class LiveStrategyRunner:
    """Manages live strategy execution with state checkpointing and parameter hot-reloading."""

    def __init__(
        self,
        feed: LiveStreamFeed,
        strategy: Strategy,
        initial_cash: float = 100_000.0,
        checkpoint_path: Path | str | None = None,
    ) -> None:
        self.feed = feed
        self.strategy = strategy
        self.engine = Engine(feed=feed, strategy=strategy, initial_cash=initial_cash)
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else None
        self._last_checkpoint: dict[str, Any] = {}

    def update_parameters(self, new_params: dict[str, Any]) -> None:
        """Hot-reload strategy hyper-parameters without losing open position state."""
        for param_name, param_value in new_params.items():
            if hasattr(self.strategy, param_name):
                setattr(self.strategy, param_name, param_value)

    def checkpoint_state(self) -> dict[str, Any]:
        """Capture current portfolio holdings, cash balance, and strategy state."""
        portfolio = self.engine.portfolio
        positions = {}
        for sym, pos in portfolio.positions.items():
            positions[sym] = {
                "qty": pos.qty,
                "avg_price": pos.avg_price,
            }

        strategy_attrs = {}
        for k, v in self.strategy.__dict__.items():
            if isinstance(v, (int, float, str, bool, list, dict)) and not k.startswith("_"):
                strategy_attrs[k] = v

        state = {
            "cash": portfolio.cash,
            "positions": positions,
            "n_events": self.engine._event_count,
            "strategy_params": strategy_attrs,
        }

        self._last_checkpoint = state
        if self.checkpoint_path:
            self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

        return state

    def restore_state(self, state: dict[str, Any] | None = None) -> None:
        """Restore cash, positions, and strategy parameters from checkpoint state."""
        if state is None and self.checkpoint_path and self.checkpoint_path.exists():
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                state = json.load(f)

        if not state:
            return

        portfolio = self.engine.portfolio
        if "cash" in state:
            portfolio.cash = float(state["cash"])

        if "positions" in state:
            for sym, pos_data in state["positions"].items():
                if sym not in portfolio._positions:
                    portfolio._positions[sym] = Position(symbol=sym)
                pos = portfolio._positions[sym]
                pos.qty = float(pos_data["qty"])
                pos.avg_price = float(pos_data["avg_price"])

        if "strategy_params" in state:
            self.update_parameters(state["strategy_params"])

        self._last_checkpoint = state

    def run(self) -> BacktestResult:
        """Execute the live strategy loop."""
        return self.engine.run()
