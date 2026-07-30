"""Tests for Volatility-Adjusted Mean Reversion & StatArb Strategy Pipeline."""

import pytest
import pandas as pd
import numpy as np
import polars as pl

from scripts.download_yfinance import download_yfinance_polars, build_ssbt_feed_from_yfinance
from ssbt.data.feed import InMemoryFeed
from ssbt.backtest.adapter import BacktestAdapter
from ssbt.optimization.space import ParameterSpace, ChoiceParam
from ssbt.optimization.grid_search import GridSearchOptimizer
from ssbt.optimization.walk_forward import WalkForwardOptimizer
from strategies_vault.volatility_mean_reversion import VolatilityAdjustedMeanReversionStrategy
from strategies_vault.statarb_pairs import StatArbPairsStrategy


@pytest.fixture
def mock_ohlcv_pd():
    """Generate 100 bars of synthetic OHLCV data."""
    dates = pd.date_range("2025-01-01", periods=100, freq="D")
    np.random.seed(42)
    close = 100.0 + np.cumsum(np.random.randn(100))
    high = close + np.random.rand(100) * 2.0
    low = close - np.random.rand(100) * 2.0
    open_p = close + np.random.randn(100) * 0.5
    volume = np.full(100, 10000.0)

    return pd.DataFrame({
        "Open": open_p,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume
    }, index=dates)


def test_external_yfinance_polars_schema(mock_ohlcv_pd):
    pl_df = download_yfinance_polars("AAPL", period="10d", interval="1d", _raw_df=mock_ohlcv_pd.head(10))
    assert isinstance(pl_df, pl.DataFrame)
    required_cols = {"timestamp", "open", "high", "low", "close", "volume", "symbol"}
    assert required_cols.issubset(set(pl_df.columns))
    assert len(pl_df) == 10
    assert pl_df["symbol"][0] == "AAPL"


def test_volatility_mean_reversion_execution(mock_ohlcv_pd):
    pl_df = download_yfinance_polars("AAPL", _raw_df=mock_ohlcv_pd)
    feed = InMemoryFeed(pl_df, symbol="AAPL")

    strat = VolatilityAdjustedMeanReversionStrategy(
        lookback=10, z_thresh=1.0, atr_period=5, atr_mult=1.5, risk_pct=0.0015, initial_balance=5000.0
    )
    assert strat.max_risk_dollars == 7.50

    adapter = BacktestAdapter(initial_cash=5000.0)
    res = adapter.run_backtest(feed, strat)

    assert res is not None
    assert "metrics" in res
    assert "raw_result" in res
    raw = res["raw_result"]
    assert hasattr(raw, "total_return")


def test_statarb_pairs_execution(mock_ohlcv_pd):
    pl_df = download_yfinance_polars("PAIR_SPREAD", _raw_df=mock_ohlcv_pd)
    feed = InMemoryFeed(pl_df, symbol="PAIR_SPREAD")

    strat = StatArbPairsStrategy(
        lookback=15, z_thresh=1.0, atr_mult=2.0, risk_pct=0.0015, initial_balance=5000.0
    )
    assert strat.max_risk_dollars == 7.50

    adapter = BacktestAdapter(initial_cash=5000.0)
    res = adapter.run_backtest(feed, strat)

    assert res is not None
    assert "metrics" in res


def test_grid_search_and_walk_forward_pipeline(mock_ohlcv_pd):
    pl_df = download_yfinance_polars("AAPL", _raw_df=mock_ohlcv_pd)
    feed = InMemoryFeed(pl_df, symbol="AAPL")

    param_space = ParameterSpace([
        ChoiceParam(name="atr_mult", choices=[1.5, 2.0]),
        ChoiceParam(name="lookback", choices=[10, 15]),
    ])

    # Grid Search Trailing Stop Sweeps
    grid_opt = GridSearchOptimizer(
        strategy_cls=VolatilityAdjustedMeanReversionStrategy,
        param_space=param_space,
        initial_cash=5000.0,
    )
    grid_res = grid_opt.optimize(feed)
    assert grid_res.best_params is not None
    assert "atr_mult" in grid_res.best_params
    assert len(grid_res.all_trials) == 4

    # Walk Forward Rolling Analysis
    wf_opt = WalkForwardOptimizer(
        strategy_cls=VolatilityAdjustedMeanReversionStrategy,
        param_space=param_space,
        is_bars=40,
        oos_bars=15,
        initial_cash=5000.0,
    )
    wf_res = wf_opt.run(feed)

    assert wf_res is not None
    assert len(wf_res.windows) > 0
    assert hasattr(wf_res, "wfe_ratio")
    assert hasattr(wf_res, "overall_oos_sharpe")

