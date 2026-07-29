"""Unit tests for Parameter Optimization & Walk-Forward Engine."""

import pytest
import polars as pl
import numpy as np

from ssbt import (
    Strategy, Side, Bar, InMemoryFeed,
    ParameterSpace, IntParam, FloatParam, ChoiceParam,
    GridSearchOptimizer, WalkForwardOptimizer,
)


class DummyCrossStrategy(Strategy):
    def __init__(self, fast: int = 5, slow: int = 20):
        super().__init__()
        self.fast = fast
        self.slow = slow
        self.prices = []

    def on_bar(self, bar: Bar, engine) -> None:
        self.prices.append(bar.close)
        if len(self.prices) < self.slow:
            return
        fast_ma = np.mean(self.prices[-self.fast:])
        slow_ma = np.mean(self.prices[-self.slow:])

        if fast_ma > slow_ma and self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.BUY, qty=1.0))
        elif fast_ma < slow_ma and not self.is_flat(engine, bar.symbol):
            engine.submit_order(self.market_order(bar.symbol, Side.SELL, qty=1.0))


@pytest.fixture
def sample_market_df() -> pl.DataFrame:
    np.random.seed(42)
    n = 300
    prices = 100.0 + np.cumsum(np.random.randn(n) * 0.5)
    timestamps = list(range(1000, 1000 + n * 60, 60))

    return pl.DataFrame({
        "timestamp": timestamps,
        "symbol": ["GC=F"] * n,
        "open": prices,
        "high": prices + 0.5,
        "low": prices - 0.5,
        "close": prices,
        "volume": [100.0] * n,
    })


def test_parameter_space_generation():
    space = ParameterSpace()
    space.add(IntParam("fast", start=5, stop=15, step=5))
    space.add(IntParam("slow", start=20, stop=30, step=10))

    grid = space.generate_grid()
    assert len(grid) == 3 * 2  # [5, 10, 15] x [20, 30]
    assert grid[0] == {"fast": 5, "slow": 20}


def test_grid_search_optimizer(sample_market_df):
    space = ParameterSpace()
    space.add(IntParam("fast", start=3, stop=6, step=3))
    space.add(IntParam("slow", start=10, stop=20, step=10))

    feed = InMemoryFeed(sample_market_df, symbol="GC=F")
    opt = GridSearchOptimizer(strategy_cls=DummyCrossStrategy, param_space=space)
    res = opt.optimize(feed)

    assert res.best_params is not None
    assert len(res.all_trials) == 4
    assert res.dsr_score >= 0.0
    assert res.pbo_score >= 0.0


def test_walk_forward_optimizer(sample_market_df):
    space = ParameterSpace()
    space.add(IntParam("fast", start=3, stop=5, step=2))
    space.add(IntParam("slow", start=10, stop=15, step=5))

    feed = InMemoryFeed(sample_market_df, symbol="GC=F")
    wf_opt = WalkForwardOptimizer(
        strategy_cls=DummyCrossStrategy,
        param_space=space,
        is_bars=100,
        oos_bars=40,
    )

    wf_res = wf_opt.run(feed)
    assert len(wf_res.windows) >= 3
    assert len(wf_res.stitched_oos_equity) > 0
    assert isinstance(wf_res.wfe_ratio, float)
