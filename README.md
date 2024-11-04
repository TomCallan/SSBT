# SSBT 🚀

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A flexible, extensible backtesting framework for trading strategies in Python.

```
📦 SSBT/
├── 📂 SSBT/
│   ├── 📄 __init__.py
│   ├── 📄 backtester.py
│   ├── 📄 position.py
│   ├── 📄 risk.py
│   ├── 📄 strategy.py
│   ├── 📄 types.py
│   └── 📄 utils.py
├── 📂 examples/
│   ├── 📄 MovingAverageCrossover.py
├── 📄 setup.py
├── 📄 requirements.txt
├── 📄 LICENSE
└── 📄 README.md
```

## Features 🌟

- Clean, modular architecture for easy extension
- Built-in position and risk management
- Support for multiple asset types
- Comprehensive performance metrics
- Flexible strategy development
- Efficient backtesting engine
- Built-in visualization tools

## Installation 🛠️
Currently, SSBT is only available for installation by cloning the GitHub repository and using it directly:

```bash
git clone https://github.com/TomCallan/SSBT.git  
cd SSBT
```

## Quick Start 🚀

Here's a simple example using a Moving Average Crossover strategy:

```python
from SSBT import Backtester, MovingAverageCrossover
import yfinance as yf

# Get some data
data = yf.download('BTC-USD', start='2022-01-01', end='2023-01-01')

# Create strategy
strategy = MovingAverageCrossover(parameters={
    'fast_period': 10,
    'slow_period': 30
})

# Initialize and run backtest
backtester = Backtester(data, strategy)
results = backtester.run()

# Print results
print(f"Total Profit: ${results['total_profit']:,.2f}")
print(f"Win Rate: {results['win_rate']:.1%}")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
```

## Example Output 📊

```
Total Trades: 24
Profitable Trades: 14
Win Rate: 58.3%
Total Profit: $12,453.21
Average Profit: $518.88
Profit Factor: 1.76
Max Drawdown: 15.2%
Sharpe Ratio: 1.43
Average Trade Duration: 3 days 14:23:11
```

## Creating Custom Strategies 🎯

Implementing your own strategy is straightforward:

```python
from SSBT import Strategy, Signal, SignalType
import pandas as pd

class RSIStrategy(Strategy):
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        df = data.copy()
        df['RSI'] = self.calculate_rsi(df['close'], 
                                     period=self.parameters.get('rsi_period', 14))
        return df
    
    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        signals = []
        for i in range(1, len(data)):
            if data['RSI'].iloc[i-1] < 30 and data['RSI'].iloc[i] >= 30:
                signals.append(Signal(
                    type=SignalType.ENTRY_LONG,
                    price=data['close'].iloc[i],
                    timestamp=data.index[i]
                ))
            elif data['RSI'].iloc[i-1] > 70 and data['RSI'].iloc[i] <= 70:
                signals.append(Signal(
                    type=SignalType.EXIT_LONG,
                    price=data['close'].iloc[i],
                    timestamp=data.index[i]
                ))
        return signals
```

## Risk Management 🛡️

The framework includes built-in risk management features:

```python
from SSBT import RiskManager, PositionManager

# Configure risk parameters
risk_manager = RiskManager(
    max_drawdown=0.20,  # 20% maximum drawdown
    max_position_size=0.10  # 10% maximum position size
)

# Configure position sizing
position_manager = PositionManager(
    initial_capital=100000.0
)

# Use in backtest
backtester = Backtester(
    data=data,
    strategy=strategy,
    risk_manager=risk_manager,
    position_manager=position_manager
)
```

## Performance Visualization 📈

```python
from SSBT.utils import plot_equity_curve

# Run backtest
results = backtester.run()

# Plot results
plot_equity_curve(results['equity_curve'], results['drawdown_curve'])
```

![Performance Charts](https://github.com/tomcallan/SSBT/raw/main/docs/images/performance.png)

## Contributing 🤝

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License 📝

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments 🙏

- Inspired by various open-source backtesting frameworks
- Built with Python's excellent data science stack
- Special thanks to all contributors
