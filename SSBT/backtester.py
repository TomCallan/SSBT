from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from .types import Signal, SignalType, Position, Trade
from .position import PositionManager
from .risk import RiskManager
from .strategy import Strategy

class Backtester:
    """Main backtesting engine"""
    def __init__(self, 
                 data: pd.DataFrame,
                 strategy: Strategy,
                 position_manager: Optional[PositionManager] = None,
                 risk_manager: Optional[RiskManager] = None,
                 commission: float = 0.001,
                 slippage: float = 0.0001):
        
        self.data = data
        self.strategy = strategy
        self.position_manager = position_manager or PositionManager()
        self.risk_manager = risk_manager or RiskManager()
        self.commission = commission
        self.slippage = slippage
        
        self.trades: List[Trade] = []
        self.current_trade: Optional[Trade] = None
        self.equity_curve = pd.Series(index=data.index, dtype=float)
        
    def run(self) -> Dict[str, Any]:
        """Execute backtest and return results"""