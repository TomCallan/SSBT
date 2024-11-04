from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Union, Any
import pandas as pd

class Position(Enum):
    """Enum for position types"""
    LONG = 1
    SHORT = -1
    FLAT = 0

class SignalType(Enum):
    """Enum for signal types"""
    ENTRY_LONG = 1
    ENTRY_SHORT = -1
    EXIT_LONG = 2
    EXIT_SHORT = -2
    
@dataclass
class Signal:
    """Signal data class for strategy signals"""
    type: SignalType
    price: float
    timestamp: Union[datetime, pd.Timestamp]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Trade:
    """Trade data class for tracking individual trades"""
    entry_price: float
    entry_time: Union[datetime, pd.Timestamp]
    position: Position
    size: float = 1.0
    exit_price: Optional[float] = None
    exit_time: Optional[Union[datetime, pd.Timestamp]] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_open(self) -> bool:
        return self.exit_time is None
    
    @property
    def duration(self) -> pd.Timedelta:
        if not self.exit_time:
            return pd.Timedelta(0)
        return self.exit_time - self.entry_time
    
    @property
    def profit(self) -> float:
        if not self.exit_price:
            return 0
        multiplier = 1 if self.position == Position.LONG else -1
        return (self.exit_price - self.entry_price) * multiplier * self.size