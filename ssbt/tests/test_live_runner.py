"""Unit tests for LiveStrategyRunner, checkpointing, and parameter hot-reloading."""

from pathlib import Path
import pytest

from ssbt import Engine, Strategy, Side, LiveStreamFeed, LiveStrategyRunner
from ssbt.core.portfolio import Position


class ParamTestStrategy(Strategy):
    def __init__(self, fast_period: int = 10, slow_period: int = 30) -> None:
        self.fast_period = fast_period
        self.slow_period = slow_period

    def on_bar(self, bar, engine: Engine) -> None:
        pass


def test_live_strategy_runner_checkpoint_and_restore(tmp_path: Path):
    checkpoint_file = tmp_path / "strategy_state.json"
    feed = LiveStreamFeed(symbols="BTCUSD", timeout=0.1)

    strategy = ParamTestStrategy(fast_period=15, slow_period=45)
    runner = LiveStrategyRunner(feed=feed, strategy=strategy, initial_cash=250_000.0, checkpoint_path=checkpoint_file)

    # Manually modify cash and positions to simulate active trading
    runner.engine.portfolio.cash = 240_000.0
    runner.engine.portfolio._positions["BTCUSD"] = Position(symbol="BTCUSD", qty=2.5, avg_price=50_000.0)

    state = runner.checkpoint_state()
    assert checkpoint_file.exists()
    assert state["cash"] == 240_000.0
    assert state["positions"]["BTCUSD"]["qty"] == 2.5
    assert state["strategy_params"]["fast_period"] == 15

    # Create fresh strategy & runner and restore state
    new_strategy = ParamTestStrategy(fast_period=5, slow_period=10)
    new_runner = LiveStrategyRunner(feed=feed, strategy=new_strategy, initial_cash=100_000.0, checkpoint_path=checkpoint_file)

    new_runner.restore_state()
    assert new_runner.engine.portfolio.cash == 240_000.0
    assert new_runner.engine.portfolio.positions["BTCUSD"].qty == 2.5
    assert new_strategy.fast_period == 15
    assert new_strategy.slow_period == 45


def test_live_strategy_runner_hot_reload():
    feed = LiveStreamFeed(symbols="ETHUSD", timeout=0.1)
    strategy = ParamTestStrategy(fast_period=10, slow_period=30)
    runner = LiveStrategyRunner(feed=feed, strategy=strategy, initial_cash=100_000.0)

    runner.update_parameters({"fast_period": 20, "slow_period": 60})
    assert strategy.fast_period == 20
    assert strategy.slow_period == 60
