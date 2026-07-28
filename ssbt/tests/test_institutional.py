"""Unit tests for institutional hardening modules: DSR/PBO, microstructure, and capacity models."""

import pytest
import numpy as np
from ssbt import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    monte_carlo_trade_permutation,
    ImpactModel,
    LiquidityCapModel,
    BorrowCostModel,
    RealisticExecutionEngine,
    VolatilityTargetingOverlay,
    StrategyCapacityAnalyzer,
    Side,
)


def test_deflated_sharpe_ratio():
    dsr_high = deflated_sharpe_ratio(observed_sharpe=2.5, var_sharpes=0.1, n_trials=5, returns_len=252)
    assert dsr_high > 0.95

    dsr_low = deflated_sharpe_ratio(observed_sharpe=0.1, var_sharpes=0.5, n_trials=100, returns_len=50)
    assert dsr_low < 0.5


def test_probability_of_backtest_overfitting():
    np.random.seed(42)
    returns_matrix = np.random.normal(0, 0.01, size=(100, 10))
    pbo = probability_of_backtest_overfitting(returns_matrix)
    assert 0.0 <= pbo <= 1.0


def test_monte_carlo_trade_permutation():
    pnls = [50.0, -20.0, 100.0, -30.0, 80.0] * 5
    res = monte_carlo_trade_permutation(pnls, initial_cash=5000.0, n_iterations=100)
    assert res["median_final_equity"] > 5000.0
    assert res["ci_95_lower"] <= res["median_final_equity"] <= res["ci_95_upper"]


def test_impact_model():
    impact = ImpactModel(gamma=0.5)
    cost = impact.calculate_impact(price=100.0, qty=1000.0, adv=100000.0, volatility=0.02)
    assert cost > 0.0


def test_liquidity_cap_model():
    cap = LiquidityCapModel(max_adv_pct=0.10)
    qty, is_capped = cap.cap_quantity(requested_qty=5000.0, bar_volume=10000.0)
    assert qty == 1000.0
    assert is_capped is True


def test_borrow_cost_model():
    borrow = BorrowCostModel(annual_borrow_rate=0.02)
    cost = borrow.calculate_borrow_cost(notional=100000.0, holding_days=365.0)
    assert abs(cost - 2000.0) < 1e-3


def test_realistic_execution_engine():
    engine = RealisticExecutionEngine()
    res = engine.process_execution(price=100.0, qty=10.0, side=Side.BUY, bar_volume=1000.0, volatility=0.01)
    assert res["executed_price"] > 100.0
    assert res["commission_dollars"] > 0.0


def test_volatility_targeting_overlay():
    overlay = VolatilityTargetingOverlay(target_volatility=0.12)
    returns = np.random.normal(0, 0.02, 50)
    scale = overlay.get_scaling_factor(returns)
    assert 0.2 <= scale <= 2.0


def test_strategy_capacity_analyzer():
    analyzer = StrategyCapacityAnalyzer(target_min_sharpe=1.0)
    cap = analyzer.estimate_capacity(base_sharpe=2.0, annual_adv_dollars=100_000_000.0)
    assert cap > 0.0
