"""Portfolio Risk Budgeting, Volatility Targeting, and Strategy Capacity Analyzer for SSBT.
"""

from __future__ import annotations

import numpy as np


class VolatilityTargetingOverlay:
    """Dynamically scales strategy position sizes to target constant portfolio volatility (e.g. 12% annualized)."""

    def __init__(self, target_volatility: float = 0.12, lookback: int = 20, max_leverage: float = 2.0):
        self.target_volatility = target_volatility
        self.lookback = lookback
        self.max_leverage = max_leverage

    def get_scaling_factor(self, recent_returns: np.ndarray, periods_per_year: int = 252) -> float:
        if len(recent_returns) < 5:
            return 1.0
        
        realized_vol = np.std(recent_returns[-self.lookback:], ddof=1) * np.sqrt(periods_per_year)
        if realized_vol <= 0:
            return 1.0

        raw_factor = self.target_volatility / realized_vol
        return float(np.clip(raw_factor, 0.2, self.max_leverage))


class StrategyCapacityAnalyzer:
    """Estimates maximum strategy AUM capacity before market impact degrades Sharpe ratio below target threshold."""

    def __init__(self, target_min_sharpe: float = 1.0):
        self.target_min_sharpe = target_min_sharpe

    def estimate_capacity(
        self,
        base_sharpe: float,
        annual_adv_dollars: float,
        turnover_per_year: float = 12.0,
        impact_gamma: float = 0.5,
    ) -> float:
        """Estimate maximum capital capacity in dollars before impact reduces Sharpe ratio below target_min_sharpe."""
        if base_sharpe <= self.target_min_sharpe or annual_adv_dollars <= 0:
            return 0.0

        # Excess Sharpe capacity
        sharpe_headroom = base_sharpe - self.target_min_sharpe
        # Maximum allowable annual impact loss percentage
        max_impact_pct = sharpe_headroom * 0.05
        
        # Max capacity formula based on Participation Rate vs Impact
        max_capital = annual_adv_dollars * ((max_impact_pct / (impact_gamma * turnover_per_year)) ** 2)
        return float(np.maximum(max_capital, 0.0))
