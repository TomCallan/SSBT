"""Market Microstructure & Execution Realism Models for SSBT.

Implements realistic transaction cost, market impact, liquidity participation caps,
and short position borrow fee modeling.
"""

from __future__ import annotations

import numpy as np
from ssbt.core.events import Side


class ImpactModel:
    """Square-root market impact model: Impact = gamma * volatility * sqrt(Qty / ADV)."""

    def __init__(self, gamma: float = 0.5):
        self.gamma = gamma

    def calculate_impact(self, price: float, qty: float, adv: float, volatility: float) -> float:
        if adv <= 0 or qty <= 0:
            return 0.0
        participation_rate = qty / adv
        impact_pct = self.gamma * volatility * np.sqrt(participation_rate)
        return float(price * impact_pct)


class LiquidityCapModel:
    """Restricts max execution quantity per bar to a maximum participation percentage of bar ADV (e.g. max 10% ADV)."""

    def __init__(self, max_adv_pct: float = 0.10):
        self.max_adv_pct = max_adv_pct

    def cap_quantity(self, requested_qty: float, bar_volume: float) -> tuple[float, bool]:
        max_allowed = bar_volume * self.max_adv_pct
        if requested_qty > max_allowed:
            return max(max_allowed, 0.0), True  # Partial fill capped
        return requested_qty, False


class BorrowCostModel:
    """Calculates short position borrow fee financing costs based on annual borrow rate."""

    def __init__(self, annual_borrow_rate: float = 0.01):  # 1% annual fee standard borrow
        self.annual_borrow_rate = annual_borrow_rate

    def calculate_borrow_cost(self, notional: float, holding_days: float) -> float:
        if notional <= 0 or holding_days <= 0:
            return 0.0
        return float(notional * (self.annual_borrow_rate / 365.0) * holding_days)


class RealisticExecutionEngine:
    """Combined Execution Realism Handler applying spread, slippage, market impact, and borrow costs."""

    def __init__(
        self,
        base_slippage_bps: float = 1.0,
        commission_bps: float = 1.0,
        impact_model: ImpactModel | None = None,
        liquidity_cap_model: LiquidityCapModel | None = None,
        borrow_cost_model: BorrowCostModel | None = None,
    ):
        self.base_slippage_bps = base_slippage_bps
        self.commission_bps = commission_bps
        self.impact_model = impact_model or ImpactModel()
        self.liquidity_cap_model = liquidity_cap_model or LiquidityCapModel()
        self.borrow_cost_model = borrow_cost_model or BorrowCostModel()

    def process_execution(
        self,
        price: float,
        qty: float,
        side: Side,
        bar_volume: float = 100_000.0,
        volatility: float = 0.01,
    ) -> dict[str, float | bool]:
        # 1. Apply liquidity participation cap
        exec_qty, is_partially_filled = self.liquidity_cap_model.cap_quantity(qty, bar_volume)

        # 2. Base slippage
        base_slip = price * (self.base_slippage_bps / 10000.0)

        # 3. Market impact
        impact = self.impact_model.calculate_impact(price, exec_qty, bar_volume, volatility)

        total_slip = base_slip + impact
        executed_price = price + total_slip if side == Side.BUY else price - total_slip

        # 4. Commission
        commission = price * exec_qty * (self.commission_bps / 10000.0)

        return {
            "executed_price": float(executed_price),
            "executed_qty": float(exec_qty),
            "slippage_dollars": float(total_slip * exec_qty),
            "commission_dollars": float(commission),
            "is_partially_filled": is_partially_filled,
        }
