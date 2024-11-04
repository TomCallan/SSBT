from typing import Optional
from .types import Signal
from .position import PositionManager

class RiskManager:
    """Handles risk management and position sizing"""
    def __init__(self, 
                 max_drawdown: float = 0.2, 
                 max_position_size: float = 0.1,
                 max_positions: int = 5):
        self.max_drawdown = max_drawdown
        self.max_position_size = max_position_size
        self.max_positions = max_positions
        self.peak_capital = 0.0
        
    def validate_trade(self, signal: Signal, position_manager: PositionManager) -> bool:
        """Validate if trade meets risk parameters"""
        # Update peak capital
        self.peak_capital = max(self.peak_capital, position_manager.current_capital)
        
        # Check drawdown
        current_drawdown = 1 - (position_manager.current_capital / self.peak_capital)
        if current_drawdown > self.max_drawdown:
            return False
            
        # Check position limits
        if position_manager.total_positions >= self.max_positions:
            return False
            
        # Check position size
        position_size = position_manager.get_position_size(signal, signal.price)
        if position_size / position_manager.current_capital > self.max_position_size:
            return False
            
        return True
        
    def calculate_stop_loss(self, signal: Signal, atr: float, 
                          multiplier: float = 2.0) -> float:
        """Calculate stop loss based on ATR"""
        if signal.type == SignalType.ENTRY_LONG:
            return signal.price - (atr * multiplier)
        return signal.price + (atr * multiplier)
        
    def calculate_position_size(self, signal: Signal, 
                              position_manager: PositionManager,
                              stop_loss: Optional[float] = None,
                              risk_per_trade: float = 0.02) -> float:
        """Calculate position size based on risk parameters and stop loss"""
        if stop_loss:
            risk_amount = position_manager.current_capital * risk_per_trade
            price_risk = abs(signal.price - stop_loss)
            return risk_amount / price_risk
        return position_manager.get_position_size(signal, signal.price, risk_per_trade)