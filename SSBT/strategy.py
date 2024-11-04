from abc import ABC, abstractmethod
from typing import Dict, List, Any
import pandas as pd
from .types import Signal, SignalType, Position

class Strategy(ABC):
    """Abstract base class for trading strategies"""
    def __init__(self, parameters: Dict[str, Any] = None):
        self.parameters = parameters or {}
        
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """Generate trading signals from data"""
        pass
    
    @abstractmethod
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate strategy-specific indicators"""
        pass

class MovingAverageCrossover(Strategy):
    """Example strategy using moving average crossover"""
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        # Skip if indicators are already calculated
        if 'MA_fast' not in df.columns:
            df['MA_fast'] = df['close'].rolling(
                self.parameters.get('fast_period', 10)).mean()
        if 'MA_slow' not in df.columns:
            df['MA_slow'] = df['close'].rolling(
                self.parameters.get('slow_period', 30)).mean()
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        signals = []
        current_position = Position.FLAT
        
        for i in range(1, len(data)):
            fast_prev = data['MA_fast'].iloc[i-1]
            fast_curr = data['MA_fast'].iloc[i]
            slow_prev = data['MA_slow'].iloc[i-1]
            slow_curr = data['MA_slow'].iloc[i]
            
            # Skip if any indicator is NaN
            if pd.isna(fast_curr) or pd.isna(slow_curr) or \
               pd.isna(fast_prev) or pd.isna(slow_prev):
                continue
                
            # Bullish crossover
            if fast_prev <= slow_prev and fast_curr > slow_curr:
                # If we're short, exit first
                if current_position == Position.SHORT:
                    signals.append(Signal(
                        type=SignalType.EXIT_SHORT,
                        price=data['close'].iloc[i],
                        timestamp=data.index[i]
                    ))
                # Then enter long
                signals.append(Signal(
                    type=SignalType.ENTRY_LONG,
                    price=data['close'].iloc[i],
                    timestamp=data.index[i]
                ))
                current_position = Position.LONG
            
            # Bearish crossover
            elif fast_prev >= slow_prev and fast_curr < slow_curr:
                # If we're long, exit first
                if current_position == Position.LONG:
                    signals.append(Signal(
                        type=SignalType.EXIT_LONG,
                        price=data['close'].iloc[i],
                        timestamp=data.index[i]
                    ))
                # Then enter short
                signals.append(Signal(
                    type=SignalType.ENTRY_SHORT,
                    price=data['close'].iloc[i],
                    timestamp=data.index[i]
                ))
                current_position = Position.SHORT
                
        # Close any remaining position at the end
        if current_position == Position.LONG:
            signals.append(Signal(
                type=SignalType.EXIT_LONG,
                price=data['close'].iloc[-1],
                timestamp=data.index[-1]
            ))
        elif current_position == Position.SHORT:
            signals.append(Signal(
                type=SignalType.EXIT_SHORT,
                price=data['close'].iloc[-1],
                timestamp=data.index[-1]
            ))
                
        return signals