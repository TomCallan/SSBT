from collections import defaultdict
from typing import Dict
from .types import Position, Signal, Trade

class PositionManager:
    """Manages position sizing and risk management"""
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, Position] = defaultdict(lambda: Position.FLAT)
        
    def get_position_size(self, signal: Signal, price: float, 
                         risk_per_trade: float = 0.02) -> float:
        """Calculate position size based on risk parameters"""
        risk_amount = self.current_capital * risk_per_trade
        return risk_amount / price
        
    def update_capital(self, trade: Trade) -> None:
        """Update capital based on closed trade"""
        self.current_capital += trade.profit
        
    def get_current_position(self, symbol: str = "default") -> Position:
        """Get current position for a symbol"""
        return self.positions[symbol]
        
    def set_position(self, position: Position, symbol: str = "default") -> None:
        """Set position for a symbol"""
        self.positions[symbol] = position
        
    @property
    def total_positions(self) -> int:
        """Get total number of open positions"""
        return sum(1 for pos in self.positions.values() if pos != Position.FLAT)